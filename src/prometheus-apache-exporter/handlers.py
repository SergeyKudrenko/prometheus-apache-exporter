import tornado.web

class metricHandler(tornado.web.RequestHandler):
    """ Tornado Handler for /metrics endpoint """
    def initialize(self, ref_object):
        self.obj = ref_object

    def get(self):
        self.obj.scrape()
        value = self.obj.generate_latest_scrape()
        self.write(value)

    def on_finish(self):
        self.obj = None
