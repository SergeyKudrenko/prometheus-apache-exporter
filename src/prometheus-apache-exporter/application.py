import os
import tornado.web
import tornado.escape
import tornado.ioloop
from exporter import exporter 
from handlers import metricHandler
from healthz import livenessProbeHandler, readinessProbeHandler

if __name__ == '__main__':
    exporter = exporter(os.environ['APACHE_EXPORTER_URL'])

    application = tornado.web.Application([
                    (r"/healthz/up", livenessProbeHandler),
                    (r"/healthz/ready", readinessProbeHandler, {"ref_object": exporter}),
                    (r"/metrics", metricHandler, {"ref_object": exporter})])

    application.listen(9345)
    tornado.ioloop.IOLoop.instance().start()
