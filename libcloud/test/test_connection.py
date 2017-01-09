# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one or more§
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import socket
import sys
import ssl

from mock import Mock, patch

from libcloud.test import unittest
from libcloud.common.base import Connection
from libcloud.httplib_ssl import LibcloudBaseConnection
from libcloud.httplib_ssl import LibcloudConnection
from libcloud.utils.misc import retry


class BaseConnectionClassTestCase(unittest.TestCase):
    def test_parse_proxy_url(self):
        conn = LibcloudBaseConnection()

        proxy_url = 'http://127.0.0.1:3128'
        result = conn._parse_proxy_url(proxy_url=proxy_url)
        self.assertEqual(result[0], 'http')
        self.assertEqual(result[1], '127.0.0.1')
        self.assertEqual(result[2], 3128)
        self.assertEqual(result[3], None)
        self.assertEqual(result[4], None)

        proxy_url = 'http://user1:pass1@127.0.0.1:3128'
        result = conn._parse_proxy_url(proxy_url=proxy_url)
        self.assertEqual(result[0], 'http')
        self.assertEqual(result[1], '127.0.0.1')
        self.assertEqual(result[2], 3128)
        self.assertEqual(result[3], 'user1')
        self.assertEqual(result[4], 'pass1')

        proxy_url = 'https://127.0.0.1:3128'
        expected_msg = 'Only http proxies are supported'
        self.assertRaisesRegexp(ValueError, expected_msg,
                                conn._parse_proxy_url,
                                proxy_url=proxy_url)

        proxy_url = 'http://127.0.0.1'
        expected_msg = 'proxy_url must be in the following format'
        self.assertRaisesRegexp(ValueError, expected_msg,
                                conn._parse_proxy_url,
                                proxy_url=proxy_url)

        proxy_url = 'http://@127.0.0.1:3128'
        expected_msg = 'URL is in an invalid format'
        self.assertRaisesRegexp(ValueError, expected_msg,
                                conn._parse_proxy_url,
                                proxy_url=proxy_url)

        proxy_url = 'http://user@127.0.0.1:3128'
        expected_msg = 'URL is in an invalid format'
        self.assertRaisesRegexp(ValueError, expected_msg,
                                conn._parse_proxy_url,
                                proxy_url=proxy_url)

    def test_constructor(self):
        conn = LibcloudConnection(host='localhost', port=80)
        self.assertEqual(conn.proxy_scheme, None)
        self.assertEqual(conn.proxy_host, None)
        self.assertEqual(conn.proxy_port, None)

        proxy_url = 'http://127.0.0.3:3128'
        conn.set_http_proxy(proxy_url=proxy_url)
        self.assertEqual(conn.proxy_scheme, 'http')
        self.assertEqual(conn.proxy_host, '127.0.0.3')
        self.assertEqual(conn.proxy_port, 3128)

        proxy_url = 'http://127.0.0.4:3128'
        conn = LibcloudConnection(host='localhost', port=80,
                                  proxy_url=proxy_url)
        self.assertEqual(conn.proxy_scheme, 'http')
        self.assertEqual(conn.proxy_host, '127.0.0.4')
        self.assertEqual(conn.proxy_port, 3128)

        os.environ['http_proxy'] = proxy_url
        proxy_url = 'http://127.0.0.5:3128'
        conn = LibcloudConnection(host='localhost', port=80,
                                  proxy_url=proxy_url)
        self.assertEqual(conn.proxy_scheme, 'http')
        self.assertEqual(conn.proxy_host, '127.0.0.5')
        self.assertEqual(conn.proxy_port, 3128)

    def test_connection_to_unusual_port(self):
        conn = LibcloudConnection(host='localhost', port=8080)
        self.assertEqual(conn.proxy_scheme, None)
        self.assertEqual(conn.proxy_host, None)
        self.assertEqual(conn.proxy_port, None)
        self.assertEqual(conn.host, 'http://localhost:8080')

        conn = LibcloudConnection(host='localhost', port=80)
        self.assertEqual(conn.host, 'http://localhost')


class ConnectionClassTestCase(unittest.TestCase):
    def setUp(self):
        self.originalConnect = Connection.connect
        self.originalResponseCls = Connection.responseCls

        Connection.connect = Mock()
        Connection.responseCls = Mock()
        Connection.allow_insecure = True

    def tearDown(self):
        Connection.connect = self.originalConnect
        Connection.responseCls = Connection.responseCls
        Connection.allow_insecure = True

    def test_dont_allow_insecure(self):
        Connection.allow_insecure = True
        Connection(secure=False)

        Connection.allow_insecure = False

        expected_msg = (r'Non https connections are not allowed \(use '
                        'secure=True\)')
        self.assertRaisesRegexp(ValueError, expected_msg, Connection,
                                secure=False)

    def test_cache_busting(self):
        params1 = {'foo1': 'bar1', 'foo2': 'bar2'}
        params2 = [('foo1', 'bar1'), ('foo2', 'bar2')]

        con = Connection()
        con.connection = Mock()
        con.pre_connect_hook = Mock()
        con.pre_connect_hook.return_value = {}, {}
        con.cache_busting = False

        con.request(action='/path', params=params1)
        args, kwargs = con.pre_connect_hook.call_args
        self.assertFalse('cache-busting' in args[0])
        self.assertEqual(args[0], params1)

        con.request(action='/path', params=params2)
        args, kwargs = con.pre_connect_hook.call_args
        self.assertFalse('cache-busting' in args[0])
        self.assertEqual(args[0], params2)

        con.cache_busting = True

        con.request(action='/path', params=params1)
        args, kwargs = con.pre_connect_hook.call_args
        self.assertTrue('cache-busting' in args[0])

        con.request(action='/path', params=params2)
        args, kwargs = con.pre_connect_hook.call_args
        self.assertTrue('cache-busting' in args[0][len(params2)])

    def test_context_is_reset_after_request_has_finished(self):
        context = {'foo': 'bar'}

        def responseCls(connection, response):
            connection.called = True
            self.assertEqual(connection.context, context)

        con = Connection()
        con.called = False
        con.connection = Mock()
        con.responseCls = responseCls

        con.set_context(context)
        self.assertEqual(con.context, context)

        con.request('/')

        # Context should have been reset
        self.assertTrue(con.called)
        self.assertEqual(con.context, {})

        # Context should also be reset if a method inside request throws
        con = Connection(timeout=1, retry_delay=0.1)
        con.connection = Mock()

        con.set_context(context)
        self.assertEqual(con.context, context)
        con.connection.request = Mock(side_effect=ssl.SSLError())

        try:
            con.request('/')
        except ssl.SSLError:
            pass

        self.assertEqual(con.context, {})

        con.connection = Mock()
        con.set_context(context)
        self.assertEqual(con.context, context)

        con.responseCls = Mock(side_effect=ValueError())

        try:
            con.request('/')
        except ValueError:
            pass

        self.assertEqual(con.context, {})

    def _raise_socket_error(self):
        raise socket.gaierror('')

    def test_retry_with_sleep(self):
        con = Connection()
        con.connection = Mock()
        connect_method = 'libcloud.common.base.Connection.request'

        with patch(connect_method) as mock_connect:
            mock_connect.__name__ = 'mock_connect'
            with self.assertRaises(socket.gaierror):
                mock_connect.side_effect = socket.gaierror('')
                retry_request = retry(timeout=1, retry_delay=.1,
                                      backoff=1)
                retry_request(con.request)(action='/')

            self.assertGreater(mock_connect.call_count, 1,
                               'Retry logic failed')

    def test_retry_with_timeout(self):
        con = Connection()
        con.connection = Mock()
        connect_method = 'libcloud.common.base.Connection.request'

        with patch(connect_method) as mock_connect:
            mock_connect.__name__ = 'mock_connect'
            with self.assertRaises(socket.gaierror):
                mock_connect.side_effect = socket.gaierror('')
                retry_request = retry(timeout=2, retry_delay=.1,
                                      backoff=1)
                retry_request(con.request)(action='/')

            self.assertGreater(mock_connect.call_count, 1,
                               'Retry logic failed')

    def test_retry_with_backoff(self):
        con = Connection()
        con.connection = Mock()
        connect_method = 'libcloud.common.base.Connection.request'

        with patch(connect_method) as mock_connect:
            mock_connect.__name__ = 'mock_connect'
            with self.assertRaises(socket.gaierror):
                mock_connect.side_effect = socket.gaierror('')
                retry_request = retry(timeout=2, retry_delay=.1,
                                      backoff=1)
                retry_request(con.request)(action='/')

            self.assertGreater(mock_connect.call_count, 1,
                               'Retry logic failed')

if __name__ == '__main__':
    sys.exit(unittest.main())
