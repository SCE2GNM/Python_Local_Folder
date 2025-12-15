# write a function that takes two numbers, adds them, and prints the result
# i wonder what happens now... why aren't isn't this line of code showing under 'changes'?

def add_numbers(num1, num2):
    result = num1 + num2
    print(f"The sum of {num1} and {num2} is: {result}")


import backtrader as bt

class MyStrategy(bt.Strategy):
    def __init__(self):
        self.dataclose = self.datas[0].close

    def next(self):
        if self.dataclose[0] > self.dataclose[-1]:
            self.buy()

def run_backtest():
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MyStrategy)

    # Create a Data Feed
    data = bt.feeds.YahooFinanceCSVData(
        dataname='../orcl-1995-2014.txt',
        fromdate=datetime.datetime(2000, 1, 1),
        todate=datetime.datetime(2000, 12, 31),
        reverse=False)

    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

if __name__ == '__main__':
    import datetime
    run_backtest()
