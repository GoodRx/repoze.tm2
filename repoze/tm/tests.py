import unittest
import sys
import transaction

class TestTM(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.tm import TM
        return TM

    def _makeOne(self, app):
        return self._getTargetClass()(app)

    def test_ekey_inserted(self):
        app = DummyApplication()
        tm = self._makeOne(app)
        from repoze.tm import ekey
        env = {}
        tm(env, None)
        self.failUnless(ekey in env)

    def test_committed(self):
        resource = DummyResource()
        app = DummyApplication(resource)
        tm = self._makeOne(app)
        result = tm({}, None)
        self.assertEqual(result, ['hello'])
        self.assertEqual(resource.committed, True)
        self.assertEqual(resource.aborted, False)

    def test_aborted_via_doom(self):
        resource = DummyResource()
        app = DummyApplication(resource, doom=True)
        tm = self._makeOne(app)
        result = tm({}, None)
        self.assertEqual(result, ['hello'])
        self.assertEqual(transaction.isDoomed(), False)
        self.assertEqual(resource.committed, False)
        self.assertEqual(resource.aborted, True)

    def test_aborted_via_exception(self):
        resource = DummyResource()
        app = DummyApplication(resource, exception=True)
        tm = self._makeOne(app)
        self.assertRaises(ValueError, tm, {}, None)
        self.assertEqual(resource.committed, False)
        self.assertEqual(resource.aborted, True)
        
    def test_aborted_via_exception_and_doom(self):
        resource = DummyResource()
        app = DummyApplication(resource, exception=True, doom=True)
        tm = self._makeOne(app)
        self.assertRaises(ValueError, tm, {}, None)
        self.assertEqual(resource.committed, False)
        self.assertEqual(resource.aborted, True)

    def test_cleanup_on_commit(self):
        dummycalled = []
        def dummy():
            dummycalled.append(True)
        env = {}
        resource = DummyResource()
        app = DummyApplication(resource, exception=False, doom=False,
                               register=dummy)
        tm = self._makeOne(app)
        tm(env, None)
        self.assertEqual(resource.committed, True)
        self.assertEqual(resource.aborted, False)
        self.assertEqual(dummycalled, [True])
        
    def test_cleanup_on_abort(self):
        dummycalled = []
        def dummy():
            dummycalled.append(True)
        env = {}
        resource = DummyResource()
        app = DummyApplication(resource, exception=True, doom=False,
                               register=dummy)
        tm = self._makeOne(app)
        self.assertRaises(ValueError, tm, env, None)
        self.assertEqual(resource.committed, False)
        self.assertEqual(resource.aborted, True)
        self.assertEqual(dummycalled, [True])

class TestAfterEnd(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.tm import AfterEnd
        return AfterEnd

    def _makeOne(self):
        return self._getTargetClass()()

    def test_register(self):
        registry = self._makeOne()
        func = lambda *x: None
        txn = DummyTransaction()
        registry.register(func, txn)
        self.assertEqual(getattr(txn, registry.key), [func])

    def test_unregister_exists(self):
        registry = self._makeOne()
        func = lambda *x: None
        txn = DummyTransaction()
        registry.register(func, txn)
        self.assertEqual(getattr(txn, registry.key), [func])
        registry.unregister(func, txn)
        self.failIf(hasattr(txn, registry.key))
        
    def test_unregister_notexists(self):
        registry = self._makeOne()
        func = lambda *x: None
        txn = DummyTransaction()
        setattr(txn, registry.key, [None])
        registry.unregister(func, txn)
        self.assertEqual(getattr(txn, registry.key), [None])

class UtilityFunctionTests(unittest.TestCase):
    def test_isActive(self):
        from repoze.tm import ekey
        from repoze.tm import isActive
        self.assertEqual(isActive({ekey:True}), True)
        self.assertEqual(isActive({}), False)

class DummyTransaction:
    pass

class DummyApplication:
    def __init__(self, resource=None, doom=False, exception=False,
                 register=None):
        self.resource = resource
        self.doom = doom
        self.exception = exception
        self.register = register
        
    def __call__(self, environ, start_response):
        t = transaction.get()
        if self.resource:
            t.join(self.resource)
        if self.register:
            from repoze.tm import after_end
            after_end.register(self.register, t)
        if self.doom:
            t.doom()
        if self.exception:
            raise ValueError('raising')
        return ['hello']

class DummyResource:
    committed = False
    aborted = False
    
    def sortKey(self):
        return 1

    tpc_finish = tpc_abort = tpc_vote = tpc_begin = lambda *arg: None

    def commit(self, txn):
        self.committed = True

    def abort(self, txn):
        self.aborted = True

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
