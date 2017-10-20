# coding: utf-8

from datetime import datetime
import logging
import sys
from urllib import quote

from apscheduler.schedulers.tornado import TornadoScheduler
from apscheduler.jobstores.base import JobLookupError
from pymongo import MongoClient
from redis import from_url
from tornado import httpserver
from tornado import ioloop
from tornado import web
from tornado.web import RequestHandler


redis_url = "redis://内网地址:6379"
# redis_url = "redis://127.0.0.1:6379"
redis = from_url(redis_url, db=2, max_connections=10)

MONGODB_HOST_PORT = "内网地址:27017"
MONGODB_PASSWORD = ""
COL_RULES = "timerules"


def get_mongodb_database(database, user="third"):
    url = "mongodb://{0}:{1}@{2}/{3}".format(
        user, quote(MONGODB_PASSWORD), MONGODB_HOST_PORT, database
    )
    client = MongoClient(host=url, maxPoolSize=5, minPoolSize=1)
    return client.get_default_database()


def task(struct, key, value):
    if struct == "set":
        redis.sadd(key, value)
    elif struct == "list":
        redis.rpush(key, value)


def format_trigger(string):
    string = string.strip()
    if string[0] == "T":  # interval
        args = dict()
        start = 1
        for i, c in enumerate(string):
            if c == "D":
                args["days"] = int(string[start:i])
                start = i+1
            elif c == "H":
                args["hours"] = int(string[start:i])
                start = i + 1
            elif c == "M":
                args["minutes"] = int(string[start:i])
                start = i + 1
            elif c == "S":
                args["seconds"] = int(string[start:i])
                start = i + 1
            else:
                pass
        return "interval", args
    elif ";" in string:  # cron
        fields = string.strip().split(";")
        args = {
            "month": fields[0],
            "day": fields[1],
            "hour": fields[2],
            "minute": fields[3],
            "second": fields[4],
        }
        return "cron", args
    else:  # date
        return "date", {"run_date": datetime.strptime(string, "%Y-%m-%d %H:%M:%S")}


class TaskHandler(RequestHandler):

    def get(self, *args, **kwargs):
        ids = self.get_arguments("id")
        results = {"jobs": list()}
        if ids:
            for _id in ids:
                job = self.application.sdr.get_job(job_id=_id)
                if job:
                    next_time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                    results["jobs"].append({"id": job.id, "name": job.name, "next": next_time})
        else:
            for job in self.application.sdr.get_jobs():
                next_time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                results["jobs"].append({"id": job.id, "name": job.name, "next": next_time})
        self.write(results)

    def post(self, *args, **kwargs):
        _id = self.get_argument("id")
        rule = self.get_argument("rule")
        key = self.get_argument("key")
        value = self.get_argument("value")
        struct = self.get_argument("struct")
        if not (_id or rule or key or value or struct):
            self.write({"code": 400, "message": "invalid params"})
        else:
            trigger, params = format_trigger(rule)
            self.application.sdr.add_job(
                task,
                trigger=trigger,
                args=[struct, key, value],
                id=_id,
                replace_existing=True,
                **params
            )
            data = {"_id": _id, "rule": rule, "key": key, "value": value,
                    "struct": struct}
            if trigger != "date":
                self.store(data)
        self.write({"code": 200, "message": "add job %s success" % _id})


    def delete(self, *args, **kwargs):
        _id = self.get_argument("id")
        try:
            self.application.sdr.remove_job(job_id=_id)
            self.remove(_id)
            self.write({"code": 200, "message": "remove job %s success" % _id})
        except JobLookupError:
            self.write({"code": 404, "message": "no such job:%s" % _id})

    def store(self, data):
        col = self.application.db[COL_RULES]
        query = {"_id": data["_id"]}
        if col.count(query):
            col.delete_one(query)
        data["time"] = datetime.now()
        col.insert_one(data)

    def remove(self, _id):
        col = self.application.db[COL_RULES]
        query = {"_id": _id}
        col.delete_one(query)


class Application(web.Application):

    def __init__(self):
        handlers = [
            ("/tasks", TaskHandler),
        ]
        defaults = {
            "coalesce": True,
            "max_instances": 5,
            "misfire_grace_time": 120,
            "replace_existing": True
        }
        scheduler = TornadoScheduler(job_defaults=defaults)
        scheduler.start()
        self.sdr = scheduler
        self.db = get_mongodb_database("thirdparty", "third")
        init_schedule_task(scheduler, self.db)
        web.Application.__init__(self, handlers=handlers)


def init_schedule_task(scheduler, db):
    col = db[COL_RULES]
    rules = col.find({})
    for rule in rules:
        trigger, params = format_trigger(rule["rule"])
        scheduler.add_job(
            task,
            trigger=trigger,
            args=[rule["struct"], rule["key"], rule["value"]],
            id=rule["_id"],
            replace_existing=True,
            **params
        )
        logging.info("add %s job rule %s" % (rule["_id"], rule["rule"]))


def main():
    http_server = httpserver.HTTPServer(Application())
    address = sys.argv[1]
    address = address.split(":")
    host = address[0]
    port = address[1]
    http_server.listen(port=port, address=host)
    ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        filename="log-app.log",
                        filemode="a+")
    main()
