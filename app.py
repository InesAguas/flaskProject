from flask import *
from flask_socketio import SocketIO
import json, eventlet, threading, time
from datetime import datetime, date, timedelta
from sqlalchemy import *
from weather import Weather
from sensor import Sensor

#activates multiprocessing in eventlet for threading
eventlet.monkey_patch()
#database engine
db = create_engine("postgresql://a2020155202:a2020155202@aid.estgoh.ipc.pt:5432/db2020155202")
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

#database tables
sensor_data = Table('sensor_data', MetaData(db),
                       Column('id', Integer, primary_key=True),
                       Column('value', Integer),
                       Column('date', DateTime(timezone=False)))

days_raining = Table('days_raining', MetaData(db),
                     Column('id', Integer, primary_key=True),
                     Column('date', Date),
                     Column('rain', String))

watering = Table('watering', MetaData(db),
                     Column('id', Integer, primary_key=True),
                     Column('date', Date))

#eventlet is used by default
socketio = SocketIO(app)

weather = Weather(db, days_raining)
sensor = Sensor(db, sensor_data, days_raining, watering, socketio)

#route for the webpage, sends last 25 data recollected from sensor
@app.route("/")
def hello_world():
    """
        route for the webpage, hello_world is called when someone accesses the route
        :return: renders the page index.html
            with data being the last 25 values for the sensor
            and labels the time for each value
    """
    data = []
    labels = []
    with db.connect() as conn:
        statement = sensor_data.select().order_by(text("date DESC")).fetch(25)
        rs = conn.execute(statement)
        for r in rs:
            data.append(r.value)
            labels.append(r.date.strftime("%H:%M:%S"))
        data.reverse()
        labels.reverse()
    return render_template('index.html', data=data, labels=labels)


#send weather information on connection
@socketio.on('connect')
def first_data():
    """
    first_data is called when a client connects to the server
    this function calls weather and sensor functions to update the database
    it also broadcasts weather data to clients
    """
    weather.insertDaysNotRaining()
    wateringTimes()
    sensor.deleteOldValues()
    now = weather.oneHour()
    multiple = weather.multipleDays()
    socketio.emit('weather', json.dumps({"now": now, "multiple": multiple}))


def water():
    """
    this is target function for one thread
    it calls the function wateringTimes every 5 minutes
    """
    while True:
        wateringTimes()
        time.sleep(300)

def wateringTimes():
    """
    this function uses the last sensor value weather predictions
    to determine when the sprinkler will be active
    it broadcasts the next time the sprinkler will be active, the last time it was and if it's active now
    """
    with db.connect() as conn:
        waternow = False
        statement = sensor_data.select().order_by(text("date DESC")).fetch(1)
        sens = conn.execute(statement)
        if sens.first() is not None:
            sens = conn.execute(statement).one()
        else:
            #if there's no data for the sensor, broadcasts default values and stops function
            socketio.emit('watering',json.dumps({"date": "N/A", "lastwater": "N/A", "waternow": waternow}, default=str))
            return
        st = days_raining.select().order_by(text("date DESC")).fetch(4)
        rs = conn.execute(st)
        rain = []
        for r in rs:
            rain.append(r)
        if sens.value <= 20:
            if rain[-1][-1] == "No":
                datewatering = date.today()
                #if last sensor value is less than 20 and it didn't rain today, sprinkler will be active today
                d = datetime.now()
                if d.hour == 16 and 0 <= d.minute < 30:
                    #if it's between 16:00 and 16:30, sprinkler is currently active
                    waternow = True
                    st = watering.select().where(text("date = '" + str(d) + "'"))
                    r = conn.execute(st)
                    if r.first() is None:
                        st = watering.insert().values(date="now()")
                        conn.execute(st)
            elif rain[-2][-1] == "No":
                datewatering = date.today() + timedelta(days=1)
                # if last sensor value is less than 20 and it won't rain tomorrow, sprinkler will be active tomorrow
            else:
                datewatering = date.today() + timedelta(days=2)
                # if last sensor value is less than 20 and tomorrow will rain, sprinkler will be active the day after tomorrow
        elif 20 < sens.value <= 40:
            if rain[-2][-1] == "No" and rain[-3][-1] == "No":
                # rega amanha
                datewatering = date.today() + timedelta(days=1)
                # if last sensor value is between 21 and 40 and it's not raining tomorrow and after tomorrow, sprinkler will be active tomorrow
            elif rain[-3][-1] != "No":
                # rega depois de depois de amanha
                datewatering = date.today() + timedelta(days=3)
                # if last sensor value is between 21 and 40 and it's raining after tomorrow, sprinkler will be active in 3 days
            else:
                datewatering = date.today() + timedelta(days=2)
                # rega depois de amanha
                # if last sensor value is between 21 and 40 and it's raining tomorrow but not after tomorrow, sprinkler will be active in 2 days
        else:
            if rain[0][-1] != "No":
                datewatering = date.today() + timedelta(days=4)
                # rega daqui a 4 dias
                # if last sensor value is more than 40 and it's raining after tomorrow, sprinkler will be active in 4 days
            else:
                # rega daqui a 3 dias
                datewatering = date.today() + timedelta(days=3)
                # if last sensor value is more than 40 and it's NOT raining after tomorrow, sprinkler will be active in 3 days
        statement = watering.select().order_by(text("date DESC")).fetch(1)
        rs = conn.execute(statement)
        value = rs.first()
        if value is None:
            lastwater = "N/A"
        else:
            #last time the sprinkler was active
            lastwater = value[1]
        conn.close()
    socketio.emit('watering', json.dumps({"date": datewatering, "lastwater": lastwater, "waternow":waternow}, default=str))

if __name__ == '__main__':
    """
    main function, updates database and starts threads
    """
    weather.insertDaysNotRaining()
    thread1 = threading.Thread(target=water)
    thread1.start()
    sensor.thr.start()
    socketio.run(app)