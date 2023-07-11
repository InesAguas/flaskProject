import requests
from datetime import date, timedelta


class Weather:

    def __init__(self, db, days_raining):
        """
        Constructor for the class Weather
        :param db: database engine
        :param days_raining: table days_raining
        """
        #base url for requests
        self.baseurl = "http://dataservice.accuweather.com/forecasts/v1/"
        #apikey for accuweather
        self.apikey = "6lPaQp4RcuMAlGBpKPD4YF7gUer8e26h"
        #second apikey in case first one is out of requests (limit 50 daily)
        #self.apikey = "ocVLMyFRp4vy8O5FKzyxch5QSkgpAhYo"
        #city key for accuweather
        self.citykey = "272831"
        self.db = db
        self.days_raining = days_raining

    def insertMaybeRaining(self, i):
        """
        used to insert in table days_raining that it might rain on a certain day
        :param i: number of days after today for the date
        """
        with self.db.connect() as conn:
            dateq = date.today() + timedelta(days=i)
            statement = self.days_raining.select().where(self.days_raining.c.date == dateq)
            try:
                #if there's already data for that day and the column rain has value "No", changes value to "Maybe"
                rs = conn.execute(statement).one()
                if rs.rain == "No":
                    statement = self.days_raining.update().where(self.days_raining.c.date == dateq).values(rain="Maybe")
                    conn.execute(statement)
            except:
                #exception is called when there's no data for that day, so data is inserted
                statement = self.days_raining.insert().values(date=dateq, rain="Maybe")
                conn.execute(statement)

    #fills data in table days_raining to make sure we have data for the next 3 days
    def insertDaysNotRaining(self):
        """
        inserts static data in database, to make sure database has the values that need to be accessed by other functions
        """
        #range is 4 because we want data for 4 days
        for i in range(4):
            dateq = date.today() + timedelta(days=i)
            with self.db.connect() as conn:
                #select statement for the date wanted
                st = self.days_raining.select().where(self.days_raining.c.date == dateq)
                rs = conn.execute(st)
                #if no data is found for that date, adds data
                if rs.first() is None:
                    statement = self.days_raining.insert().values(date=dateq, rain="No")
                    conn.execute(statement)

    def multipleDays(self):
        """
        requests data for 5 days from accuweather api (only uses 4 days)

        :return: weather data for 4 days (minimum and maximum temperatures), including today
        """
        url = self.baseurl + "daily/5day/" + self.citykey + "?apikey=" + self.apikey
        response = requests.get(url).json()
        data = []
        for i in range(4):
            #inserts values for min and max temp in array data
            day = [round((response["DailyForecasts"][i]["Temperature"]["Minimum"]["Value"]-32)*5/9),
                   round((response["DailyForecasts"][i]["Temperature"]["Maximum"]["Value"]-32)*5/9)]
            data.append(day)
            #checks if there's a chance of rain during the day
            if response["DailyForecasts"][i]["Day"]["HasPrecipitation"]:
                if response["DailyForecasts"][i]["Day"]["PrecipitationType"] == "Rain":
                    #if chance of rain and date is after today, inserts in database
                    if i > 0:
                        self.insertMaybeRaining(i)
            #checks if there's a chance of rain at night
            if response["DailyForecasts"][i]["Night"]["HasPrecipitation"]:
                if response["DailyForecasts"][i]["Night"]["PrecipitationType"] == "Rain":
                    # if chance of rain and date is after today, inserts in database
                    if i > 0:
                        self.insertMaybeRaining(i)
        return data

    def oneHour(self):
        """
        requests data for 1 hour from accuweather api
        if it's raining, updates database
        :return: data for that hour, including a phrase, the current temperature and precipitation probability
        """
        url = self.baseurl + "hourly/1hour/" + self.citykey + "?apikey=" + self.apikey
        response = requests.get(url).json()
        data = [response[0]["IconPhrase"], round((response[0]["Temperature"]["Value"]-32)*5/9), response[0]["PrecipitationProbability"]]
        #checks if value HasPrecipitaion is true
        if response[0]["HasPrecipitation"]:
            #if precipitation type is Rain, updates db
            if response[0]["PrecipitationType"] == "Rain":
                with self.db.connect() as conn:
                    statement = self.days_raining.select().where(self.days_raining.c.date == "now()")
                    try:
                        #if there's already a value for today, updates the value of column rain to "Yes"
                        rs = conn.execute(statement).one()
                        if rs.rain != "Yes":
                            statement = self.days_raining.update().where(self.days_raining.c.date == "now()").values(rain="Yes")
                            conn.execute(statement)
                    except:
                        #except is called when no data is found, so data is inserted
                        statement = self.days_raining.insert().values(date="now()", rain="Yes")
                        conn.execute(statement)
        return data
