import threading, time, random, json
from datetime import date, timedelta, datetime
from sqlalchemy import text

class Sensor:
    def __init__(self, db, sensor_data, days_raining, watering, socketio):
        """
        constructor for the class Sensor
        :param db: database engine
        :param sensor_data: table sensor_data
        :param days_raining: table days_raining
        :param watering: table watering
        :param socketio: socket (used for broadcasting)
        """
        self.db = db
        self.sensor_data = sensor_data
        self.days_raining = days_raining
        self.watering = watering
        #iniciates a thread calling the function sensor_update
        self.thr = threading.Thread(target=self.sensor_update)
        self.socketio = socketio

    def sensor_update(self):
        """
        target function for a thread, simulates a soil humidity sensor

        a random number between two values is generated for humidity
        those two values are determined by checking the days it rained and days the sprinkler was active

        broadcasts the value collected by the sensor every 5 minutes
        """
        while True:
            with self.db.connect() as conn:
                datetoday = date.today()
                dateyesterday = date.today() + timedelta(days=-1)
                st = self.days_raining.select().where(self.days_raining.c.date == datetoday)
                today = conn.execute(st).one()
                st = self.days_raining.select().where(self.days_raining.c.date == dateyesterday)
                yesterday = conn.execute(st)
                if yesterday.first() is not None:
                    yesterday = conn.execute(st).one()
                else:
                    yesterday = ["No"]
                st = self.watering.select().where(self.watering.c.date == datetoday)
                water = conn.execute(st)
                if today[-1] == "Yes" or water.first() is not None:
                    nb = random.randint(41, 90)
                else:
                    st = self.watering.select().where(self.watering.c.date == datetoday)
                    water = conn.execute(st)
                    if yesterday[-1] == "Yes" or water.first() is not None:
                        nb = random.randint(21, 40)
                    else:
                        nb = random.randint(5, 20)
                statement = self.sensor_data.insert().values(value=nb, date="now()")
                conn.execute(statement)
                conn.close()
            self.socketio.emit('soilhumidity', json.dumps({"soilhumidity": nb, "date": datetime.now().strftime("%H:%M:%S")}, default=str))
            time.sleep(300)

    def deleteOldValues(self):
        """
        this function deletes old values from the table sensor_data,
        because the sensor collects lots of data per day
        """
        dateq = datetime.now() + timedelta(days=-3)
        with self.db.connect() as conn:
            #deletes data where the date is more than 3 days old
            st = self.sensor_data.delete().where(text("date <= '" + str(dateq) + "'"))
            conn.execute(st)
            conn.close()