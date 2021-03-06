# encoding: UTF-8

"""
存在跳空缺口才开仓，如：
1. 最新价小于等于开盘价3个tick，空单止盈，反手做多
2. 最新价大于等于开盘价3个tick，多单止盈，反手做空
3. 涨幅超过1%，空单止损
4. 跌幅超过1%，多单止损
5. 每天每个合约最多开仓4次
6. 止损后不再开仓
"""

from datetime import datetime
import pandas as pd
from pHist import hist
from ctaBase import *
from ctaTemplate import CtaTemplate


########################################################################
class RealStrategy(CtaTemplate):
    """存在跳空缺口才开仓"""
    className = 'RealStrategy'
    author = 'Eleven'

    # 策略参数
    amplitude = 3  # 开仓阈值
    stopThreshold = 0.02    #止损阈值
    maxOpenCount = 4  # 最大开仓次数
    tradeVolume = 1 # 交易数量
    size = 10   # 合约大小
    tickPrice = 5 # 最小变动价格

    # 策略变量
    openCount = 0

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'amplitude',
                 'stopThreshold',
                 'tradeVolume',
                 'maxOpenCount']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'perHigh',
               'perLow',
               'status',
               'winCount',
               'lossCount',
               'opening',
               'closeing',
               'stopOpen']

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(RealStrategy, self).__init__(ctaEngine, setting)

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）
        self.perHigh = None     # 昨日最高价
        self.perLow = None      # 昨日最低价
        self.status = 0         # 策略状态
        self.openCount = 0      # 今日开仓次数
        self.opening = False    # 正在开仓
        self.stopOpen = False   # 停止开仓
        self.closeing = False   # 正在平仓
        self.winCount = 0       # 止盈次数
        self.doWin = False      # 正在止盈
        self.lossCount = 0      # 止损次数
        self.doLoss = False     # 正在止损
        self.lastOrder = None   # 最新订单回报
    # ----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'策略初始化')
        # 获取昨日最高价和最低价
        a = hist()
        a.get_K_data(self.vtSymbol, period='1d')
        self.perHigh = list(a.data['high'])[-1]
        self.perLow = list(a.data['low'])[-1]
        self.status = 0
        self.openCount = 0  # 今日开仓次数，需要保存
        self.opening = False
        self.stopOpen = False
        self.closeing = False
        self.winCount = 0
        self.doWin = False
        self.lossCount = 0
        self.doLoss = False
        self.putEvent()

    # ----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'策略启动')
        self.putEvent()

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'策略停止')
        self.putEvent()

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        if not self.trading:
            return

        if tick.openPrice > self.perHigh or tick.openPrice < self.perLow:
            self.status = 1

        # 未成交撤单
        if self.lastOrder != None and (self.lastOrder.status == u'未成交' or self.lastOrder.status == u'未知'):
            self.cancelOrder(self.lastOrder.vtOrderID)
            self.lastOrder = None
        # 完成撤单
        elif self.lastOrder != None and self.lastOrder.status == u'已撤销':
            if self.lastOrder.offset == u'开仓':
                self.opening = False
            else:
                self.closeing = False
                if self.doWin:
                    self.doWin = False
                elif self.doLoss:
                    self.doLoss = False
            self.lastOrder[tick.symbol] = None

        # 策略状态切换
        if self.status == 0:
            if self.winCount >= 2:
                self.status = 1
                self.winCount = 0
                self.writeCtaLog(u'[切换到顺势策略]成功')
                print u'[切换到顺势策略]成功'
            elif self.lossCount >= 1:
                self.stopOpen = True
        elif self.status == 1:
            if self.winCount >= 1:
                self.stopOpen = True
            elif self.lossCount >= 6:
                self.stopOpen = True

        # 执行策略
        if self.status == 0:
            self.contrarian(tick)
        elif self.status == 1:
            self.homeopathic(tick)

        # 收盘清仓
        nowTime = datetime.strptime(tick.time.split('.')[0], '%H:%M:%S').time()
        # print nowTime
        if (nowTime > datetime.strptime('14:59:30', '%H:%M:%S').time()) and (
                    nowTime <= datetime.strptime('15:00:00', '%H:%M:%S').time()):
            self.clearPosition(tick)
        self.putEvent()

    # ----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        if order.offset == u'开仓' and order.status == u'全部成交':
            self.lastOrder = None
            # self.ctaEngine.mainEngine.gatewayDict['CTP'].qryPosition()
        elif order.status == u'全部成交':
            self.lastOrder = None
            # self.ctaEngine.mainEngine.gatewayDict['CTP'].qryPosition()
            self.closeing = False
            if self.doWin:
                self.winCount += 1
                self.doWin = False
                self.writeCtaLog(u'[止盈]成功')
                print u'[止盈]成功'
            elif self.doLoss:
                self.lossCount += 1
                self.doLoss = False
                self.writeCtaLog(u'[止损]成功')
                print u'[止损]成功'
            else:
                self.writeCtaLog(u'[清仓]成功')
                print u'[清仓]成功'
        else:
            self.lastOrder[order.symbol] = order
        logContent = u'[订单回报]合约代码：%s，订单编号：%s，价格：%s，数量：%s，方向：%s，开平仓：%s，订单状态：%s，报单时间：%s' % (
            order.symbol, order.orderID, order.price, order.totalVolume, order.direction, order.offset,order.status, order.orderTime)
        self.writeCtaLog(logContent)
        print logContent
        # send_msg(logContent.encode('utf-8'))
        self.putEvent()
    # ----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        pass

    # ----------------------------------------------------------------------
    def contrarian(self, tick):
        '''逆势开仓，止盈止损'''

        highThreshold = tick.openPrice + self.tickPrice * 3
        lowThreshold = tick.openPrice - self.tickPrice * 3

        # 存在空单
        if self.pos < 0 and not self.closeing:
            if self.opening:
                self.opening = False
                self.openCount += 1
                self.writeCtaLog(u'[开空仓]成功')
                print u'[开空仓]成功'
            # 止损
            if tick.lastPrice >= tick.openPrice * (1 + self.stopThreshold):
                self.cover(tick.askPrice1, self.tradeVolume)
                self.closeing = True
                self.doLoss = True
                self.writeCtaLog(u'[空仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.askPrice1))
                print u'[空仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.askPrice1)
            # 止盈
            elif tick.lastPrice <= lowThreshold:
                self.cover(tick.askPrice1, self.tradeVolume)
                self.closeing = True
                self.doWin = True
                self.writeCtaLog(u'[空仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.askPrice1))
                print u'[空仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.askPrice1)
        # 存在多单
        elif self.pos > 0 and not self.closeing:
            if self.opening:
                self.opening = False
                self.openCount += 1
                self.writeCtaLog(u'[开多仓]成功')
                print u'[开多仓]成功'
            # 止损
            if tick.lastPrice <= tick.openPrice * (1 - self.stopThreshold):
                self.sell(tick.bidPrice1, self.tradeVolume)
                self.closeing = True
                self.doLoss = True
                self.writeCtaLog(u'[多仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.bidPrice1))
                print u'[多仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.bidPrice1)
            # 止盈
            elif tick.lastPrice >= highThreshold:
                self.sell(tick.bidPrice1, self.tradeVolume)
                self.closeing = True
                self.doWin = True
                self.writeCtaLog(u'[多仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.bidPrice1))
                print u'[多仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.bidPrice1)
        # 不存在持仓
        # elif self.pos == 0:
            # if self.closeing and self.doWin:
            #     self.closeing = False
            #     self.winCount += 1
            #     self.doWin = False
            #     self.writeCtaLog(u'[止盈]成功')
            #     print u'[止盈]成功'
            # elif self.closeing and self.doLoss:
            #     self.closeing = False
            #     self.lossCount += 1
            #     self.doLoss = False
            #     self.writeCtaLog(u'[止损]成功')
            #     print u'[止损]成功'
            # elif self.closeing:
            #     self.closeing = False
            #     self.writeCtaLog(u'[清仓]成功')
            #     print u'[清仓]成功'

        # 涨停跌停不开仓
        if tick.highPrice >= tick.upperLimit or tick.lowPrice <= tick.lowerLimit \
                or self.lossCount >= 1 or self.winCount >= 2 or self.stopOpen:
            return
        # 做多
        elif tick.lastPrice <= lowThreshold and not self.opening and not self.closeing and self.pos <= 0:
            self.buy(tick.askPrice1, self.tradeVolume)
            self.opening = True
            self.writeCtaLog(u'[开多仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1))
            print u'[开多仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1)
        # 做空
        elif tick.lastPrice >= highThreshold and not self.opening and not self.closeing and self.pos >= 0:
            self.short(tick.bidPrice1, self.tradeVolume)
            self.opening = True
            self.writeCtaLog(u'[开空仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1))
            print u'[开空仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1)

    def homeopathic(self, tick):
        '''顺势开仓，止损不止盈'''

        highThreshold = tick.openPrice + self.tickPrice * 2
        lowThreshold = tick.openPrice - self.tickPrice * 2

        # 存在空单
        if self.pos < 0 and not self.closeing:
            if self.opening:
                self.opening = False
                self.openCount += 1
                self.writeCtaLog(u'[开空仓]成功')
                print u'[开空仓]成功'
            # 止损
            if tick.lastPrice >= highThreshold:
                self.cover(tick.askPrice1, self.tradeVolume)
                self.closeing = True
                self.doLoss = True
                self.writeCtaLog(u'[空仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.askPrice1))
                print u'[空仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.askPrice1)
            # 止盈
            elif tick.lastPrice <= tick.lowerLimit:
                self.cover(tick.askPrice1, self.tradeVolume)
                self.closeing = True
                self.doWin = True
                self.writeCtaLog(u'[空仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.askPrice1))
                print u'[空仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.askPrice1)
        # 存在多单
        elif self.pos > 0 and not self.closeing:
            if self.opening:
                self.opening = False
                self.openCount += 1
                self.writeCtaLog(u'[开多仓]成功')
                print u'[开多仓]成功'
            # 止损
            if tick.lastPrice <= lowThreshold:
                self.sell(tick.bidPrice1, self.tradeVolume)
                self.closeing = True
                self.doLoss = True
                self.writeCtaLog(u'[多仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.bidPrice1))
                print u'[多仓止损]合约代码：%s，止损价格：%s' % (tick.symbol, tick.bidPrice1)
            # 止盈
            elif tick.lastPrice >= tick.upperLimit:
                self.sell(tick.bidPrice1, self.tradeVolume)
                self.closeing = True
                self.doWin = True
                self.writeCtaLog(u'[多仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.bidPrice1))
                print u'[多仓止盈]合约代码：%s，止盈价格：%s' % (tick.symbol, tick.bidPrice1)
        # 不存在持仓
        # elif self.pos == 0:
        #     if self.closeing and self.doWin:
        #         self.closeing = False
        #         self.winCount += 1
        #         self.doWin = False
        #         self.writeCtaLog(u'[止盈]成功')
        #         print u'[止盈]成功'
        #     elif self.closeing and self.doLoss:
        #         self.closeing = False
        #         self.lossCount += 1
        #         self.doLoss = False
        #         self.writeCtaLog(u'[止损]成功')
        #         print u'[止损]成功'
        #     elif self.closeing:
        #         self.closeing = False
        #         self.writeCtaLog(u'[清仓]成功')
        #         print u'[清仓]成功'

        # 涨停跌停不开仓
        if tick.highPrice >= tick.upperLimit or tick.lowPrice <= tick.lowerLimit \
                or self.lossCount >= 6 or self.winCount >= 1 or self.stopOpen:
            return
        # 做多
        elif tick.lastPrice >= highThreshold and not self.opening and not self.closeing and self.pos <= 0:
            self.buy(tick.askPrice1, self.tradeVolume)
            self.opening = True
            self.writeCtaLog(u'[开多仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1))
            print u'[开多仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1)
        # 做空
        elif tick.lastPrice <= lowThreshold and not self.opening and not self.closeing and self.pos >= 0:
            self.short(tick.bidPrice1, self.tradeVolume)
            self.opening = True
            self.writeCtaLog(u'[开空仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1))
            print u'[开空仓]合约代码：%s，开仓价格：%s' % (tick.symbol, tick.askPrice1)

    def clearPosition(self, tick):
        if self.pos > 0 and not self.closeing:
            self.closeing = True
            self.stopOpen = True
            self.sell(tick.bidPrice1, self.tradeVolume)
            self.writeCtaLog(u'[清多仓]合约代码：%s，清仓价格：%s' % (tick.symbol, tick.bidPrice1))
            print u'[清多仓]合约代码：%s，清仓价格：%s' % (tick.symbol, tick.bidPrice1)
        elif self.pos < 0 and not self.closeing:
            self.closeing = True
            self.stopOpen = True
            self.cover(tick.askPrice1, self.tradeVolume)
            self.writeCtaLog(u'[清空仓]合约代码：%s，清仓价格：%s' % (tick.symbol, tick.askPrice1))
            print u'[清空仓]合约代码：%s，清仓价格：%s' % (tick.symbol, tick.askPrice1)
        else:
            pass
