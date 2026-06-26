'''
objective: to count Profit and Loss

Version  Date        Author    Comment
================================================================================
1.0      20260613    Vincent   Flexian V1.0 baseline reset (cutoff today). Prior history archived in docs/version_history.md
1.1      20260614    Claude    Fix annualized Sharpe (span-based, correct direction/units) via _annualized_sharpe(); forcetoclosetrade now updates summary (see docs/backtest_improvements.md)
1.2      20260614    Claude    B18 fix: over-close (abnormal) branch logs average open price instead of open_price[0] (docs/core_bugs.md)

# tx-header: coin,openaction, open DT, open datetime, open price, close DT, close datetime, close price, PL, PL%, factor
# tx-detail: coin,DT,datetime,action,price,unit,factor

'''


import time
import common.gfuncs as G;
import pandas as pd;
from statistics import mean;
import csv;
import statistics as stat;



##Parameters
PLOTGRAPH=False;             #True to record data for plotgragh use   False: for production
CAPTURETRADEDETAILS=False;   #capture all trade details
RISK_FREE_RATIO=0.03;           #annual risk-free rate

def count_positive_negative(lst):
    """
    Count the percentage of positive and negative numbers in the given list.

    Args:
        lst (list): A list of numbers.

    Returns:
        tuple: A tuple containing the percentage of positive and negative numbers.
    """
    if len(lst)>0:
        positive_count = sum(1 for num in lst if num >= 0)
        negative_count = sum(1 for num in lst if num < 0)
        total_count = len(lst)
        positive_percentage = (positive_count / total_count) * 100
        negative_percentage = (negative_count / total_count) * 100
        return positive_percentage, negative_percentage
    else:
        return 0,0;

class Summary():

    def __init__(self):
        self.actions=[];
        self.pls=[];
        self.plpercents=[];
        

        pass;

    def add_data(self, action,pl_percent):
        """
        to import data for calcuation

        in:
            action(int): 1 for buy.  -1 for sell
            pl_percent(float): profit and loss % in this deal
        """
        self.actions.append(action);
        self.pls.append(pl_percent);
        pass;

    def get_details(self):
        """
        to get summary of all details
        out: [winningratio,fairratio,lossratio,winning average %,lossing average %]
            winningratio(float):
            fairratio(float):
            lossratio(float):
            winning average %(float):
            lossing average %(float):
        """

        total=len(self.pls);

        if total>0:
            winningratio,fairratio,lossratio = 0,0,0;
            winning=[];
            lossing = [];
        
            for pl in self.pls:
                if pl>0:
                    winningratio+=1;
                    winning.append(pl);
                elif pl==0:
                    fairratio+=1;
                else:
                    lossratio+=1;
                    lossing.append(pl);

            if len(winning)>0:
                mean_win=mean(winning);
            else:
                mean_win=0;

            if len(lossing)>0:
                mean_loss=mean(lossing);
            else:
                mean_loss=0;


            return winningratio/total*100, fairratio/total*100,lossratio/total*100,mean_win, mean_loss;
        else:
            return 0,0,0,0,0;

    def get_betratio(self):
        """
        to get winning ratio according to data

        out:
            winningratio(float):
            fairratio(float):
            lossratio(float):
        """
        total=len(self.pls);
        if total>0:
            winningratio,fairratio,lossratio = 0,0,0;
        
            for pl in self.pls:
                if pl>0:
                    winningratio+=1;
                elif pl==0:
                    fairratio+=1;
                else:
                    lossratio+=1;

            return winningratio/total*100, fairratio/total*100,lossratio/total*100;
        else:
            return 0,0,0;


    def get_avgamount(self):
        """
        to get win and loss average reward according to data

        out:
            winning average %(float):
            lossing average %(float):
        """
        total=len(self.pls);
        if total>0:
            winning=[];
            lossing = [];
        
            for pl in self.pls:
                if pl>0:
                    winning.append(pl);
                elif pl==0:
                    pass;
                else:
                    lossing.append(pl);

            return mean(winning), mean(lossing);
        else:
            return 0,0;

class PL():

    def __init__(self, currency,plotgraph=PLOTGRAPH,capturedetails=CAPTURETRADEDETAILS,exportfilepath_header=r"tx_header.csv",exportfilepath_details=r"tx_details.csv",days_of_trading_per_year:int=365):
        self.currency=currency;
        self.plotgraph=plotgraph;
        self.capturedetails=capturedetails;
        self.exportfilepath_header=exportfilepath_header;
        self.exportfilepath_details=exportfilepath_details;
        self.summary = Summary();
        self.last_dt=0;             #last input DT from addnew(to prevent multiple actions with the same timestamp use)
        self.days_of_trading_per_year=days_of_trading_per_year;

        self.df = {};               #transaction header
        
        if self.capturedetails:
            self.df_details = {};
        
        self.in_trade=False;            #True if in trade status now
        self.trigger=0;                 #if not trade status, record trigger action 1 or -1
        self.trigger_time=0;            #if not trade status, record trigger time

        self.buffer_header = []
        self.buffer_details = []

        #turtle incremental unit 
        self.open_price=[];             #price of trades
        self.open_unit=[];              #unit of trades
        self.open_factor=[];             #factor of trades

        
        self.last_action_is_close = False;  #True if last action is to close position
        self.last_trade_PL_percent = 0;     #last complete trade profit and loss %

        if self.plotgraph:
            self.tradelist_open =pd.DataFrame([[0,0]],
                                 index=[0],
                                 columns=['unixtime','price']);     #store time and price for graph plot

            self.tradelist_open.drop(0,inplace=True);               #plot grade use (production no need)
            self.tradelist_close= self.tradelist_open.copy();       #plot grade use (production no need)

        pass;

    def _annualized_sharpe(self, list_PL_percent, sd):
        """
        Annualized Sharpe ratio from per-trade returns (%), using the ACTUAL test span derived
        from trade open/close timestamps in self.df (so it no longer depends on a bogus 365/NoOfTX
        scaling).

            span_days        = (last close ts - first open ts) / 86400
            trades_per_year  = NoOfTX / (span_days / days_of_trading_per_year)
            Sharpe(annual)   = (mean*tpy - rf_annual) / (sd * sqrt(tpy))

        Returns 0.0 when it cannot be computed (sd==0, fewer than 2 trades, or non-positive span).
        """
        n = len(list_PL_percent)
        if sd == 0 or n < 2:
            return 0.0
        try:
            open_times = [float(row[2]) for row in self.df.values()]    # row[2] = open/trigger timestamp
            close_times = [float(row[5]) for row in self.df.values()]   # row[5] = close/settle timestamp
            span_days = (max(close_times) - min(open_times)) / 86400.0
        except Exception:
            span_days = 0
        if span_days <= 0:
            return 0.0
        years = span_days / self.days_of_trading_per_year
        if years <= 0:
            return 0.0
        trades_per_year = n / years
        rf_annual_pct = RISK_FREE_RATIO * 100.0     # RISK_FREE_RATIO is a fraction (0.03) -> percent units
        ann_return = mean(list_PL_percent) * trades_per_year
        ann_sd = sd * (trades_per_year ** 0.5)
        if ann_sd == 0:
            return 0.0
        return (ann_return - rf_annual_pct) / ann_sd

    def statistics(self):
        '''
        to get statistics of result

        out:
            NoOfTX[int],PL_percent[float]
        '''

        NoOfTX=len(self.df);

        PL_percent=0;
        for row in self.df.values():
            PL_percent+=row[9]; #9: PL_percent

        return NoOfTX,PL_percent;

    def statistics_details_custommetric(self):
        """
        return number of tx, total PL %, PL total amount, shaperatio, max negative return %
        """
        NoOfTX=len(self.df);

        PL_total=0;
        total_PL_percent=0;
        list_PL_percent=[];
        for row in self.df.values():
            PL_total+=float(row[8]); #8: PL
            list_PL_percent.append(float(row[9]));
            total_PL_percent+=float(row[9]); #9: PL_percent

        if len(list_PL_percent)>1:      #list need to have at least 2 value to have variance and SD
            sd = stat.stdev(list_PL_percent);
        else:
            sd = 0;

        max_negative_percent = min(list_PL_percent) if len(list_PL_percent)>0 else 0;

        if sd != 0 :
            pl_volatility_ratio = total_PL_percent / sd  # Custom metric
            return NoOfTX, total_PL_percent, PL_total, round(pl_volatility_ratio, 3), max_negative_percent
        else:
            return NoOfTX,total_PL_percent,PL_total,0, max_negative_percent;

    def statistics_details_advance(self):
        """
        return number of tx, total PL %, PL total amount, shaperatio, max negative return %, winning%, loss%
        """

        NoOfTX=len(self.df);
        PL_total=0;
        total_PL_percent=0;
        list_PL_percent=[];
        for row in self.df.values():
            PL_total+=float(row[8]); #8: PL
            list_PL_percent.append(float(row[9]));
            total_PL_percent+=float(row[9]); #9: PL_percent

        

        if len(list_PL_percent)>1:      #list need to have at least 2 value to have variance and SD
            sd = stat.stdev(list_PL_percent);
        else:
            sd = 0;

        max_negative_percent = min(list_PL_percent) if len(list_PL_percent)>0 else 0;

        positive, negative = count_positive_negative(list_PL_percent);

        sharpe_ratio = self._annualized_sharpe(list_PL_percent, sd)
        return NoOfTX,total_PL_percent,PL_total,sharpe_ratio, max_negative_percent, positive, negative;

    def ratiosummary(self):
        """
            out: [winningratio,fairratio,lossratio,winning average %,lossing average %]
        """
        return self.summary.get_details();

    def totalinvestamt(self):
        total_all=0;            #count all total amount with both positive and negative unit
        total_net=0;            #count only positive unit (original trigger action. Partial close unit is always negative)
        for i in range(len(self.open_price)):
            total_all += self.open_price[i]*self.open_unit[i];
            if self.open_unit[i]>0:
                total_net += self.open_price[i]*self.open_unit[i];
        return total_all,total_net;

    def get_current_unit(self):
        if len(self.open_unit)>0:
            return sum(self.open_unit);
        else:
            return 0;

    def forcetoclosetrade(self,price,now):
        if self.in_trade:
            unit=sum(self.open_unit);
            total_all,total_net=self.totalinvestamt();

            PL=(total_all-price*unit)*self.trigger*-1;
            PL_percent = round(PL/(total_net)*100,2);
            average_open_price = total_all / unit if unit != 0 else 0
        
            # Calculate weighted average factor
            if len(self.open_factor) > 0 and unit != 0:
                weighted_factor = sum(self.open_factor[i] * abs(self.open_unit[i]) for i in range(len(self.open_factor))) / unit
            else:
                weighted_factor = 1.0

            self.summary.add_data(self.trigger, PL_percent);   # keep summary stats consistent with addnew()
            # Updated header format: coin,trigger,trigger_time,trigger_DT,trigger_price,settle_time,settle_DT,settle_price,PL,PL_percent,factor
            self.df[self.trigger_time] = [self.currency,self.trigger,self.trigger_time,G.timestamp_to_str(self.trigger_time),average_open_price ,now,G.timestamp_to_str(now),price,PL,PL_percent,weighted_factor];

            if self.plotgraph:                                   #for plot graph data use
                self.tradelist_close.loc[now]=[now,price];

            #reset parameter for new trade
            self.in_trade=False;
            self.open_price=[];
            self.open_unit=[];
            self.open_factor=[];


    def addnew(self, action, price, now, unit, factor=1.0):
        """
        Add a new trade action to the P&L tracker.

        Args:
            action (int): 1 for buy (long), -1 for sell (short).
            price (float): Trade price.
            now (int): Unix timestamp of the trade.
            unit (float): Number of units traded (must be positive).
            factor (float): Trade factor/multiplier (default: 1.0).

        Raises:
            AssertionError: If action is not 1 or -1, or if unit <= 0
            Exception: If an error occurs during processing.
        """

        try:
            assert (abs(action)==1), "action only can be 1 or -1";
            assert unit>0, "unit must > 0";
        
            self.last_action_is_close=False;        #default: ensure is False for new data set come in

            if self.last_dt!=now:
                self.last_dt=now;
            else:
                now = now+1;
                self.last_dt=now;

            if self.capturedetails:
                # Modified to include factor in the details
                # coin,trigger_time,trigger_DT,action,price,unit,factor
                self.df_details[now]=[self.currency,now,G.timestamp_to_str(now),action,price,unit,factor];  
                
            if self.in_trade:           #if trade status, settle with this action

                if (action*self.trigger)==1:        #incremental increase of unit (same direction of trigger)
                    self.open_price.append(price);
                    self.open_unit.append(unit);
                    self.open_factor.append(factor);
                else:                               #close the orginal trades (opposite direction of trigger)
                    
                    unitintotal = sum(self.open_unit);
                    if round(unit,4)==round(unitintotal,4):   #if close the whole position
                        total_all,total_net=self.totalinvestamt();
                        PL=(total_all-price*unitintotal)*action;
                        PL_percent = round(PL/(total_net)*100,2);
                        average_open_price = total_all / unitintotal if unitintotal != 0 else 0
                    
                        # Calculate weighted average factor
                        if len(self.open_factor) > 0 and unitintotal != 0:
                            weighted_factor = sum(self.open_factor[i] * abs(self.open_unit[i]) for i in range(len(self.open_factor))) / unitintotal
                        else:
                            weighted_factor = 1.0
                    
                        self.last_action_is_close=True;     #it is close action
                        self.last_trade_PL_percent = PL_percent;

                        self.summary.add_data(self.trigger,PL_percent);
                        #tx header: coin,action, open DT, open datetime, open price, close DT, close datetime, close price, PL, PL%, factor
                        self.df[self.trigger_time]=[self.currency,self.trigger,self.trigger_time,G.timestamp_to_str(self.trigger_time),average_open_price,now,G.timestamp_to_str(now),price,PL,PL_percent,weighted_factor];
                
                    

                        #reset parameter for new trade
                        self.in_trade=False;
                        self.open_price=[];
                        self.open_unit=[];
                        self.open_factor=[];

                        if self.plotgraph:                                   #for plot graph data use
                            self.tradelist_close.loc[now]=[now,price];
                        pass;
                    elif round(unit,4)<round(unitintotal,4):     #partially close order 
                        self.open_price.append(price);
                        self.open_unit.append(-unit);
                        self.open_factor.append(factor);
                        pass;
                    else:                                       #over close (abnormal), regard as opposite direction and alert message
                    
                        #remaining_unit = unit-unitintotal;
                        total_all,total_net=self.totalinvestamt();
                        PL=(total_all-price*unitintotal)*action;
                        PL_percent = round(PL/(total_net)*100,2);
                        average_open_price = total_all / unitintotal if unitintotal != 0 else 0   # B18 fix: log average open, consistent with whole-close branch

                        # Calculate weighted average factor
                        if len(self.open_factor) > 0 and unitintotal != 0:
                            weighted_factor = sum(self.open_factor[i] * abs(self.open_unit[i]) for i in range(len(self.open_factor))) / unitintotal
                        else:
                            weighted_factor = 1.0

                        self.last_action_is_close=True;     #it is close action
                        self.last_trade_PL_percent = PL_percent;

                        self.summary.add_data(self.trigger,PL_percent);
                        #tx header: coin,openaction, open DT, open datetime, open price, close DT, close datetime, close price, PL, PL%, factor
                        self.df[self.trigger_time]=[self.currency, self.trigger,self.trigger_time,G.timestamp_to_str(self.trigger_time),average_open_price,now,G.timestamp_to_str(now),price,PL,PL_percent,weighted_factor];
                        if self.plotgraph:                                   #for plot graph data use
                            self.tradelist_close.loc[now]=[now,price];
                    
                        #reset parameter for new trade
                        self.in_trade=False;
                        self.open_price=[];
                        self.open_unit=[];
                        self.open_factor=[];

                        print("Abnormal Close position => Total Unit:%s     Close Unit:%s"%(unitintotal,unit));

                        pass;


            else:                       #new action 
                self.trigger=action;
                self.trigger_time=now;
                self.open_price.append(price);
                self.open_unit.append(unit);
                self.open_factor.append(factor);

                self.in_trade=True;

                if self.plotgraph:
                    self.tradelist_open.loc[now]=[now,price];

            pass;

        except Exception as ex:
            G.println('PL addnew Error:%s'%str(ex))

    def exportToFile(self):
        f = open(self.exportfilepath_header, 'a',newline='')
        writer = csv.writer(f);

        for row in self.df.values():
            writer.writerow(row);

        f.close()
        
        pass;

    def exportTXdetails(self):
        if not self.capturedetails:
            print("CAPTURETRADEDETAILS is False. Program doesn't record details")
            return

        self.buffer_details.extend(self.df_details.values())

        if len(self.buffer_details) > 0:
            self._flush_buffer("details")


    def _flush_buffer(self, buffer_type):
        filepath = self.exportfilepath_header if buffer_type == "header" else self.exportfilepath_details
        buffer = self.buffer_header if buffer_type == "header" else self.buffer_details
        with open(filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            for row in buffer:
                writer.writerow(row)
        if buffer_type == "header":
            self.buffer_header = []
        else:
            self.buffer_details = []

    def flush_all(self):  # Call at program end
        if self.buffer_header:
            self._flush_buffer("header")
        if self.buffer_details and self.capturedetails:
            self._flush_buffer("details")

    def statistics_details(self):
        NoOfTX = len(self.df)
        PL_total = 0
        total_PL_percent = 0
        list_PL_percent = []
        for row in self.df.values():
            PL_total += float(row[8])  # PL
            list_PL_percent.append(float(row[9]))  # PL_percent
            total_PL_percent += float(row[9])

        sd = stat.stdev(list_PL_percent) if len(list_PL_percent) > 1 else 0
        max_negative_percent = min(list_PL_percent) if list_PL_percent else 0

        sharpe_ratio = self._annualized_sharpe(list_PL_percent, sd)
        return NoOfTX, total_PL_percent, PL_total, round(sharpe_ratio, 3), max_negative_percent
            


if __name__ == "__main__":

    # pl = PL('ADA');
    # pl.addnew(1,1,123,100)
    # pl.addnew(1,1.1,124,100)
    # pl.addnew(-1,1.2,125,100)
    # pl.addnew(-1,1.3,126,50)
    # pl.addnew(-1,1.4,127,70)
    # print(pl.statistics())

    # pl.addnew(-1,1.4,128,100)
    # pl.addnew(-1,1.3,129,100)
    # pl.addnew(1,1.35,130,200)
    # print(pl.statistics())

    pass;