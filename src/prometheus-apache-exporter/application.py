import tornado.web
import tornado.ioloop
from collector import Collector, MetricHandler
from healthz import LivenessProbeHandler, ReadinessProbeHandler
from prometheus_client.core import REGISTRY

REGISTRY.register(Collector())

if __name__ == '__main__':
    exporter = Collector()

    application = tornado.web.Application([
                    (r"/healthz/up", LivenessProbeHandler),
                    (r"/healthz/ready", ReadinessProbeHandler, {"ref_object": exporter}),
                    (r"/metrics", MetricHandler, {"ref_object": exporter})])

    application.listen(9345)
    tornado.ioloop.IOLoop.instance().start()
