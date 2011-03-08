from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import defer
from werkzeug import routing

class KleinResource(object, Resource):
    class __metaclass__(type):
        def __init__(self, name, bases, attrs):
            inherited_rules = []
            inherited_endpoints = {}
            for base in reversed(bases):
                p = getattr(base, '__klein_params__', None)
                if p is None:
                    continue

                mapper, endpoints = p
                inherited_rules.extend(
                    rule.empty() for rule in mapper.iter_rules())
                inherited_endpoints.update(endpoints)

            routes = self.map = routing.Map(inherited_rules)
            endpoints = self.endpoints = inherited_endpoints
            self.__klein_params__ = routes, endpoints
            for value in attrs.itervalues():
                akw = getattr(value, '__klein_exposed__', None)
                if akw is None:
                    continue

                url, a, kw = akw
                rule = routing.Rule(url, *a, **kw)
                endpoints[kw['endpoint']] = value
                routes.add(rule)

    isLeaf = True

    def render(self, request):
        server_name = request.getRequestHostname()
        server_port = request.getHost().port
        if (bool(request.isSecure()), server_port) not in [
                (True, 443), (False, 80)]:
            server_name = '%s:%d' % (server_name, server_port)
        script_name = ''
        if request.prepath:
            script_name = '/' + '/'.join(request.prepath)
        path_info = ''
        if request.postpath:
            path_info = '/' + '/'.join(request.postpath)
        url_scheme = 'https' if request.isSecure() else 'http'

        mapper = self.map.bind(server_name, script_name, path_info=path_info,
            default_method=request.method, url_scheme=url_scheme)
        request.mapper = mapper
        request.url_for = mapper.build
        endpoint, kwargs = mapper.match()

        meth = self.endpoints[endpoint]
        d = defer.maybeDeferred(meth, self, request, **kwargs)
        def process(r):
            if r is not None:
                request.write(r)
                request.finish()
            return r
        d.addCallback(process)
        d.addErrback(request.processingFailed)
        return server.NOT_DONE_YET
