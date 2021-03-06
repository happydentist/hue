#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import sys

if sys.version_info[0] > 2:
  from unittest.mock import patch, Mock, MagicMock
else:
  from mock import patch, Mock, MagicMock

from nose.tools import assert_equal, assert_true, assert_raises, assert_not_equal
from nose.plugins.skip import SkipTest
from TCLIService.ttypes import TStatusCode

from beeswax.conf import MAX_NUMBER_OF_SESSIONS, CLOSE_SESSIONS
from beeswax.models import Session
from beeswax.server.hive_server2_lib import HiveServerTable, HiveServerClient

from desktop.lib.django_test_util import make_logged_in_client
from desktop.lib.test_utils import grant_access
from useradmin.models import User



LOG = logging.getLogger(__name__)


class TestHiveServerClient():

  def setUp(self):
    self.client = make_logged_in_client(username="test_hive_server2_lib", groupname="default", recreate=True, is_superuser=False)
    self.user = User.objects.get(username="test_hive_server2_lib")

    grant_access(self.user.username, self.user.username, "beeswax")

    self.query_server = {
        'principal': 'hue',
        'server_name': 'hive',
        'QUERY_TIMEOUT_S': 60,
        'auth_username': 'hue',
        'auth_password': 'hue',
        'use_sasl': True,
        'server_host': 'localhost',
        'server_port': 10000,
    }

  def test_open_session(self):
    query = Mock(
      get_query_statement=Mock(return_value=['SELECT 1']),
      settings=[]
    )

    with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
      get_client.return_value = Mock(
        OpenSession=Mock(
          return_value=Mock(
            status=Mock(
              statusCode=TStatusCode.SUCCESS_STATUS
            ),
            configuration={},
            sessionHandle=Mock(
              sessionId=Mock(
                secret=b'1',
                guid=b'1'
              )
            ),
            serverProtocolVersion=11
          )
        ),
        get_coordinator_host=Mock(return_value='hive-host')
      )
      session_count = Session.objects.filter(owner=self.user, application=self.query_server['server_name']).count()

      # Send open session
      session = HiveServerClient(self.query_server, self.user).open_session(self.user)

      assert_equal(
        session_count + 1,  # +1 as setUp resets the user which deletes cascade the sessions
        Session.objects.filter(owner=self.user, application=self.query_server['server_name']).count()
      )
      assert_equal(
        session.guid,
        Session.objects.get_session(self.user, self.query_server['server_name']).guid.encode()
      )

  def test_explain(self):
    query = Mock(
      get_query_statement=Mock(return_value=['SELECT 1']),
      settings=[]
    )

    with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
      get_client.return_value = Mock(
        OpenSession=Mock(
          return_value=Mock(
            status=Mock(
              statusCode=TStatusCode.SUCCESS_STATUS
            ),
            configuration={},
            sessionHandle=Mock(
              sessionId=Mock(
                secret=b'1',
                guid=b'1'
              )
            ),
            serverProtocolVersion=11
          )
        ),
        ExecuteStatement=Mock(
          return_value=Mock(
            status=Mock(
              statusCode=TStatusCode.SUCCESS_STATUS
            ),
          )
        ),
        FetchResults=Mock(
          return_value=Mock(
            status=Mock(
              statusCode=TStatusCode.SUCCESS_STATUS
            ),
            results=Mock(
              columns=[
                # Dump of `EXPLAIN SELECT 1`
                Mock(stringVal=Mock(values=['Plan optimized by CBO.', '', 'Stage-0', '	  Fetch Operator', '5	    limit:-1' ], nulls='')),
              ]
            ),
            schema=Mock(
              columns=[
                Mock(columnName='Explain'),
              ]
            )
          )
        ),
        GetResultSetMetadata=Mock(
          return_value=Mock(
            status=Mock(
              statusCode=TStatusCode.SUCCESS_STATUS
            ),
            results=Mock(
              columns=[
                Mock(stringVal=Mock(values=['Explain', ], nulls='')),  # Fake but ok
              ]
            ),
            schema=Mock(
              columns=[
                Mock(columnName='primitiveEntry 7'),
              ]
            )
          )
        ),
        get_coordinator_host=Mock(return_value='hive-host')
      )
      session_count = Session.objects.filter(owner=self.user, application=self.query_server['server_name']).count()

      # Send explain
      explain = HiveServerClient(self.query_server, self.user).explain(query)

      assert_equal(
        [['Plan optimized by CBO.'], [''], ['Stage-0'], ['	  Fetch Operator'], ['5	    limit:-1']],
        list(explain.rows())
      )
      assert_equal(
        session_count + 1,
        Session.objects.filter(owner=self.user, application=self.query_server['server_name']).count()
      )


class TestHiveServerTable():

  def test_cols_impala(self):

    table_results = Mock()
    table_schema = Mock()
    desc_results = Mock(
      columns=[
        # Dump of `DESCRIBE FORMATTED table`
        Mock(stringVal=Mock(values=['# col_name', '', 'code', 'description', 'total_emp', 'salary', '', '# Detailed Table Information', 'Database:', 'OwnerType:', 'Owner:', 'CreateTime:', 'LastAccessTime:', 'Retention:', 'Location:', 'Table Type:', 'Table Parameters:', '', '', '', '', '', '', '', '', '', '', '# Storage Information', 'SerDe Library:', 'InputFormat:', 'OutputFormat:', 'Compressed:', 'Num Buckets:', 'Bucket Columns:', 'Sort Columns:', 'Storage Desc Params:', ], nulls='')),
        Mock(stringVal=Mock(values=['data_type', 'NULL', 'string', 'string', 'int', 'int', 'NULL', 'NULL', 'default', 'USER', 'hive', 'Mon Nov 04 07:44:10 PST 2019', 'UNKNOWN', '0', 'hdfs://nightly7x-unsecure-1.vpc.cloudera.com:8020/warehouse/tablespace/managed/hive/sample_07', 'MANAGED_TABLE', 'NULL', 'COLUMN_STATS_ACCURATE', 'bucketing_version', 'numFiles', 'numRows', 'rawDataSize', 'totalSize', 'transactional', 'transactional_properties', 'transient_lastDdlTime', 'NULL', 'NULL', 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat', 'No', '-1', '[]', '[]', 'NULL', 'serialization.format', ], nulls='')),
        Mock(stringVal=Mock(values=['comment', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '{\"BASIC_STATS\":\"true\",\"COLUMN_STATS\":{\"code\":\"true\",\"description\":\"true\",\"salary\":\"true\",\"total_emp\":\"true\"}}', '2', '1', '822', '3288', '48445', 'true', 'insert_only', '1572882268', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '1', ], nulls='')),
      ]
    )
    desc_schema = Mock(
      columns=[
        Mock(columnName='col_name'),
        Mock(columnName='data_type'),
        Mock(columnName='comment')
      ]
    )

    table = HiveServerTable(
      table_results=table_results,
      table_schema=table_schema,
      desc_results=desc_results,
      desc_schema=desc_schema
    )

    assert_equal(len(table.cols), 4)
    assert_equal(table.cols[0], {'col_name': 'code', 'data_type': 'string', 'comment': 'NULL'})
    assert_equal(table.cols[1], {'col_name': 'description', 'data_type': 'string', 'comment': 'NULL'})
    assert_equal(table.cols[2], {'col_name': 'total_emp', 'data_type': 'int', 'comment': 'NULL'})
    assert_equal(table.cols[3], {'col_name': 'salary', 'data_type': 'int', 'comment': 'NULL'})


  def test_cols_hive_tez(self):

      table_results = Mock()
      table_schema = Mock()
      desc_results = Mock(
        columns=[
          # Dump of `DESCRIBE FORMATTED table`
          Mock(stringVal=Mock(values=['code', 'description', 'total_emp', 'salary', '', '# Detailed Table Information', 'Database:           ', 'OwnerType:          ', 'Owner:              ', 'CreateTime:         ', 'LastAccessTime:     ', 'Retention:          ', 'Location:           ', 'Table Type:         ', 'Table Parameters:', '', '', '', '', '', '', '', '', '', '', '# Storage Information', 'SerDe Library:      ', 'InputFormat:        ', 'OutputFormat:       ', 'Compressed:         ', 'Num Buckets:        ', 'Bucket Columns:     ', 'Sort Columns:       ', 'Storage Desc Params:', ], nulls='')),
          Mock(stringVal=Mock(values=['string', 'string', 'int', 'int', 'NULL', 'NULL', 'default             ', 'USER                ', 'hive                ', 'Mon Nov 04 07:44:10 PST 2019', 'UNKNOWN             ', '0', 'hdfs://nightly7x-unsecure-1.vpc.cloudera.com:8020/warehouse/tablespace/managed/hive/sample_07', 'MANAGED_TABLE       ', 'NULL', 'COLUMN_STATS_ACCURATE', 'bucketing_version   ', 'numFiles            ', 'numRows             ', 'rawDataSize         ', 'totalSize           ', 'transactional       ', 'transactional_properties', 'transient_lastDdlTime', 'NULL', 'NULL', 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat', 'No                  ', '-1', '[]                  ', '[]                  ', 'NULL', 'serialization.format', ], nulls='')),
          Mock(stringVal=Mock(values=['', '', '', '', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '{\"BASIC_STATS\":\"true\",\"COLUMN_STATS\":{\"code\":\"true\",\"description\":\"true\",\"salary\":\"true\",\"total_emp\":\"true\"}}', '2', '1', '822', '3288', '48445', 'TRUE', 'insert_only         ', '1572882268', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '1', ], nulls='')),
        ]
      )
      desc_schema = Mock(
        columns=[
          Mock(columnName='col_name'),
          Mock(columnName='data_type'),
          Mock(columnName='comment')
        ]
      )

      table = HiveServerTable(
        table_results=table_results,
        table_schema=table_schema,
        desc_results=desc_results,
        desc_schema=desc_schema
      )

      assert_equal(len(table.cols), 4)
      assert_equal(table.cols[0], {'col_name': 'code', 'data_type': 'string', 'comment': ''})
      assert_equal(table.cols[1], {'col_name': 'description', 'data_type': 'string', 'comment': ''})
      assert_equal(table.cols[2], {'col_name': 'total_emp', 'data_type': 'int', 'comment': ''})
      assert_equal(table.cols[3], {'col_name': 'salary', 'data_type': 'int', 'comment': ''})


  def test_partition_keys_impala(self):

      table_results = Mock()
      table_schema = Mock()
      desc_results = Mock(
        columns=[
          # Dump of `DESCRIBE FORMATTED table`
          Mock(stringVal=Mock(values=['# col_name', '', 'code', 'description', 'total_emp', 'salary', '', '# Partition Information', '# col_name', '', 'date', '', '# Detailed Table Information', 'Database:', 'OwnerType:', 'Owner:', 'CreateTime:', 'LastAccessTime:', 'Retention:', 'Location:', 'Table Type:', 'Table Parameters:', '', '', '', '', '', '', '', '', '', '', '# Storage Information', 'SerDe Library:', 'InputFormat:', 'OutputFormat:', 'Compressed:', 'Num Buckets:', 'Bucket Columns:', 'Sort Columns:', 'Storage Desc Params:', ], nulls='')),
          Mock(stringVal=Mock(values=['data_type', 'NULL', 'string', 'string', 'int', 'int', 'NULL', 'NULL', 'data_type', 'NULL', 'string', 'NULL', 'NULL', 'default', 'USER', 'hive', 'Mon Nov 04 07:44:10 PST 2019', 'UNKNOWN', '0', 'hdfs://nightly7x-unsecure-1.vpc.cloudera.com:8020/warehouse/tablespace/managed/hive/sample_07', 'MANAGED_TABLE', 'NULL', 'COLUMN_STATS_ACCURATE', 'bucketing_version', 'numFiles', 'numRows', 'rawDataSize', 'totalSize', 'transactional', 'transactional_properties', 'transient_lastDdlTime', 'NULL', 'NULL', 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat', 'No', '-1', '[]', '[]', 'NULL', 'serialization.format', ], nulls='')),
          Mock(stringVal=Mock(values=['comment', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'comment', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '{\"BASIC_STATS\":\"true\",\"COLUMN_STATS\":{\"code\":\"true\",\"description\":\"true\",\"salary\":\"true\",\"total_emp\":\"true\"}}', '2', '1', '822', '3288', '48445', 'true', 'insert_only', '1572882268', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '1', ], nulls='')),
        ]
      )
      desc_schema = Mock(
        columns=[
          Mock(columnName='col_name'),
          Mock(columnName='data_type'),
          Mock(columnName='comment')
        ]
      )

      table = HiveServerTable(
        table_results=table_results,
        table_schema=table_schema,
        desc_results=desc_results,
        desc_schema=desc_schema
      )

      assert_equal(len(table.partition_keys), 1)
      assert_equal(table.partition_keys[0].name, 'date')
      assert_equal(table.partition_keys[0].type, 'string')
      assert_equal(table.partition_keys[0].comment, 'NULL')


  def test_partition_keys_hive(self):

      table_results = Mock()
      table_schema = Mock()
      desc_results = Mock(
        columns=[
          # Dump of `DESCRIBE FORMATTED table`
          # Note: missing blank line below '# Partition Information'
          Mock(stringVal=Mock(values=['# col_name', '', 'code', 'description', 'total_emp', 'salary', '', '# Partition Information', '# col_name', 'date', '', '# Detailed Table Information', 'Database:', 'OwnerType:', 'Owner:', 'CreateTime:', 'LastAccessTime:', 'Retention:', 'Location:', 'Table Type:', 'Table Parameters:', '', '', '', '', '', '', '', '', '', '', '# Storage Information', 'SerDe Library:', 'InputFormat:', 'OutputFormat:', 'Compressed:', 'Num Buckets:', 'Bucket Columns:', 'Sort Columns:', 'Storage Desc Params:', ], nulls='')),
          Mock(stringVal=Mock(values=['data_type', 'NULL', 'string', 'string', 'int', 'int', 'NULL', 'NULL', 'data_type', 'string', 'NULL', 'NULL', 'default', 'USER', 'hive', 'Mon Nov 04 07:44:10 PST 2019', 'UNKNOWN', '0', 'hdfs://nightly7x-unsecure-1.vpc.cloudera.com:8020/warehouse/tablespace/managed/hive/sample_07', 'MANAGED_TABLE', 'NULL', 'COLUMN_STATS_ACCURATE', 'bucketing_version', 'numFiles', 'numRows', 'rawDataSize', 'totalSize', 'transactional', 'transactional_properties', 'transient_lastDdlTime', 'NULL', 'NULL', 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat', 'No', '-1', '[]', '[]', 'NULL', 'serialization.format', ], nulls='')),
          Mock(stringVal=Mock(values=['comment', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'comment', '', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '{\"BASIC_STATS\":\"true\",\"COLUMN_STATS\":{\"code\":\"true\",\"description\":\"true\",\"salary\":\"true\",\"total_emp\":\"true\"}}', '2', '1', '822', '3288', '48445', 'true', 'insert_only', '1572882268', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '1', ], nulls='')),
        ]
      )
      desc_schema = Mock(
        columns=[
          Mock(columnName='col_name'),
          Mock(columnName='data_type'),
          Mock(columnName='comment')
        ]
      )

      table = HiveServerTable(
        table_results=table_results,
        table_schema=table_schema,
        desc_results=desc_results,
        desc_schema=desc_schema
      )

      assert_equal(len(table.partition_keys), 1)
      assert_equal(table.partition_keys[0].name, 'date')
      assert_equal(table.partition_keys[0].type, 'string')
      assert_equal(table.partition_keys[0].comment, '')


  def test_primary_keys_hive(self):

      table_results = Mock()
      table_schema = Mock()
      desc_results = Mock(
        columns=[
          # Dump of `DESCRIBE FORMATTED table`
          Mock(stringVal=Mock(values=['# col_name', '', 'code', 'description', 'total_emp', 'salary', '', '# Partition Information', '# col_name', 'date', '', '# Detailed Table Information', 'Database:', 'OwnerType:', 'Owner:', 'CreateTime:', 'LastAccessTime:', 'Retention:', 'Location:', 'Table Type:', 'Table Parameters:', '', '', '', '', '', '', '', '', '', '', '# Storage Information', 'SerDe Library:', 'InputFormat:', 'OutputFormat:', 'Compressed:', 'Num Buckets:', 'Bucket Columns:', 'Sort Columns:', 'Storage Desc Params:', '', '', '# Constraints', '', '# Primary Key', 'Table:', 'Constraint Name:', 'Column Name:', 'Column Name:'], nulls='')),
          Mock(stringVal=Mock(values=['data_type', 'NULL', 'string', 'string', 'int', 'int', 'NULL', 'NULL', 'data_type', 'string', 'NULL', 'NULL', 'default', 'USER', 'hive', 'Mon Nov 04 07:44:10 PST 2019', 'UNKNOWN', '0', 'hdfs://nightly7x-unsecure-1.vpc.cloudera.com:8020/warehouse/tablespace/managed/hive/sample_07', 'MANAGED_TABLE', 'NULL', 'COLUMN_STATS_ACCURATE', 'bucketing_version', 'numFiles', 'numRows', 'rawDataSize', 'totalSize', 'transactional', 'transactional_properties', 'transient_lastDdlTime', 'NULL', 'NULL', 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat', 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat', 'No', '-1', '[]', '[]', 'NULL', 'serialization.format', 'NULL', 'NULL', 'NULL', 'NULL', 'default.pk', 'pk_165400321_1572980510006_0', 'id1 ', 'id2 '], nulls='')),
          Mock(stringVal=Mock(values=['comment', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'comment', '', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '{\"BASIC_STATS\":\"true\",\"COLUMN_STATS\":{\"code\":\"true\",\"description\":\"true\",\"salary\":\"true\",\"total_emp\":\"true\"}}', '2', '1', '822', '3288', '48445', 'true', 'insert_only', '1572882268', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', '1', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL', 'NULL'], nulls='')),
        ]
      )
      desc_schema = Mock(
        columns=[
          Mock(columnName='col_name'),
          Mock(columnName='data_type'),
          Mock(columnName='comment')
        ]
      )

      table = HiveServerTable(
        table_results=table_results,
        table_schema=table_schema,
        desc_results=desc_results,
        desc_schema=desc_schema
      )

      assert_equal(len(table.primary_keys), 2)
      assert_equal(table.primary_keys[0].name, 'id1')
      assert_equal(table.primary_keys[0].type, 'NULL')
      assert_equal(table.primary_keys[0].comment, 'NULL')

      assert_equal(table.primary_keys[1].name, 'id2')
      assert_equal(table.primary_keys[1].type, 'NULL')
      assert_equal(table.primary_keys[1].comment, 'NULL')

class SessionTest():
  def test_call_session_single(self):
    finish = (MAX_NUMBER_OF_SESSIONS.set_for_testing(1),
                CLOSE_SESSIONS.set_for_testing(False))
    try:
      with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
        with patch('beeswax.server.hive_server2_lib.HiveServerClient.open_session') as open_session:
          with patch('beeswax.server.hive_server2_lib.Session.objects.get_session') as get_session:
            open_session.return_value = MagicMock(status_code=0)
            get_session.return_value = None
            fn = MagicMock(attr='test')
            req = MagicMock()

            client = HiveServerClient(MagicMock(), MagicMock())
            (res, session1) = client.call(fn, req, status=None)
            open_session.assert_called_once()

            # Reuse session from argument
            (res, session2) = client.call(fn, req, status=None, session=session1)
            open_session.assert_called_once() # open_session should not be called again, because we're reusing session
            assert_equal(session1, session2)

            # Reuse session from get_session
            get_session.return_value = session1
            (res, session3) = client.call(fn, req, status=None)
            open_session.assert_called_once() # open_session should not be called again, because we're reusing session
            assert_equal(session1, session3)
    finally:
      for f in finish:
        f()

  def test_call_session_pool(self):
    finish = (MAX_NUMBER_OF_SESSIONS.set_for_testing(2),
                CLOSE_SESSIONS.set_for_testing(False))
    try:
      with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
        with patch('beeswax.server.hive_server2_lib.HiveServerClient.open_session') as open_session:
          with patch('beeswax.server.hive_server2_lib.Session.objects.get_tez_session') as get_session:
            open_session.return_value = MagicMock(status_code=0)
            get_session.return_value = None
            fn = MagicMock(return_value=MagicMock(status=MagicMock(statusCode=0)))
            req = MagicMock()

            client = HiveServerClient(MagicMock(), MagicMock())
            (res, session1) = client.call(fn, req, status=None)
            open_session.assert_called_once()

            # Reuse session from argument
            (res, session2) = client.call(fn, req, status=None, session=session1)
            open_session.assert_called_once() # open_session should not be called again, because we're reusing session
            assert_equal(session1, session2)

            # Reuse session from get_session
            get_session.return_value = session1
            (res, session3) = client.call(fn, req, status=None)
            open_session.assert_called_once() # open_session should not be called again, because we're reusing session
            assert_equal(session1, session3)
    finally:
      for f in finish:
        f()

  def test_call_session_pool_limit(self):
    finish = (MAX_NUMBER_OF_SESSIONS.set_for_testing(2),
                CLOSE_SESSIONS.set_for_testing(False))
    try:
      with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
        with patch('beeswax.server.hive_server2_lib.HiveServerClient.open_session') as open_session:
          with patch('beeswax.server.hive_server2_lib.Session.objects.get_tez_session') as get_tez_session:
            get_tez_session.side_effect=Exception('')
            open_session.return_value = MagicMock(status_code=0)
            fn = MagicMock(return_value=MagicMock(status=MagicMock(statusCode=0)))
            req = MagicMock()
            client = HiveServerClient(MagicMock(), MagicMock())
            assert_raises(Exception, client.call, fn, req, status=None)
    finally:
      for f in finish:
        f()

  def test_call_session_close_idle(self):
    finish = (MAX_NUMBER_OF_SESSIONS.set_for_testing(-1),
                CLOSE_SESSIONS.set_for_testing(True))
    try:
      with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
        with patch('beeswax.server.hive_server2_lib.HiveServerClient.open_session') as open_session:
          open_session.return_value = MagicMock(status_code=0)
          fn = MagicMock(return_value=MagicMock(status=MagicMock(statusCode=0)))
          req = MagicMock()

          client = HiveServerClient(MagicMock(), MagicMock())
          (res, session1) = client.call(fn, req, status=None)
          open_session.assert_called_once()

          # Reuse session from argument
          (res, session2) = client.call(fn, req, status=None, session=session1)
          open_session.assert_called_once() # open_session should not be called again, because we're reusing session
          assert_equal(session1, session2)

          # Create new session
          open_session.return_value = MagicMock(status_code=0)
          (res, session3) = client.call(fn, req, status=None)
          assert_equal(open_session.call_count, 2)
          assert_not_equal(session1, session3)
    finally:
      for f in finish:
        f()

  def test_call_session_close_idle_managed_queries(self):
    finish = (MAX_NUMBER_OF_SESSIONS.set_for_testing(-1),
                CLOSE_SESSIONS.set_for_testing(True))
    try:
      with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
        with patch('beeswax.server.hive_server2_lib.HiveServerClient.open_session') as open_session:
          with patch('beeswax.server.hive_server2_lib.HiveServerClient.close_session') as close_session:
            with patch('beeswax.server.hive_server2_lib.HiveServerTRowSet') as HiveServerTRowSet:
              status = MagicMock(status=MagicMock(statusCode=0))
              status_return = MagicMock(return_value=status)
              get_client.return_value = MagicMock(return_value=status, GetSchemas=status_return, FetchResults=status_return, GetResultSetMetadata=status_return, CloseOperation=status_return, ExecuteStatement=status_return, GetTables=status_return, GetColumns=status_return)

              open_session.return_value = MagicMock(status_code=0)
              client = HiveServerClient(MagicMock(), MagicMock())

              res = client.get_databases()
              assert_equal(open_session.call_count, 1)
              assert_equal(close_session.call_count, 1)

              res = client.get_database(MagicMock())
              assert_equal(open_session.call_count, 2)
              assert_equal(close_session.call_count, 2)

              res = client.get_tables_meta(MagicMock(), MagicMock())
              assert_equal(open_session.call_count, 3)
              assert_equal(close_session.call_count, 3)

              res = client.get_tables(MagicMock(), MagicMock())
              assert_equal(open_session.call_count, 4)
              assert_equal(close_session.call_count, 4)

              res = client.get_table(MagicMock(), MagicMock())
              assert_equal(open_session.call_count, 5)
              assert_equal(close_session.call_count, 5)

              res = client.get_columns(MagicMock(), MagicMock())
              assert_equal(open_session.call_count, 6)
              assert_equal(close_session.call_count, 6)

              res = client.get_partitions(MagicMock(), MagicMock()) # get_partitions does 2 requests with 1 session each
              assert_equal(open_session.call_count, 8)
              assert_equal(close_session.call_count, 8)
    finally:
      for f in finish:
        f()

  def test_call_session_close_idle_limit(self):
    finish = (MAX_NUMBER_OF_SESSIONS.set_for_testing(2),
                CLOSE_SESSIONS.set_for_testing(True))
    try:
      with patch('beeswax.server.hive_server2_lib.thrift_util.get_client') as get_client:
        with patch('beeswax.server.hive_server2_lib.HiveServerClient.open_session') as open_session:
          with patch('beeswax.server.hive_server2_lib.Session.objects.get_n_sessions') as get_n_sessions:
            get_n_sessions.return_value = [MagicMock(), MagicMock()]
            open_session.return_value = MagicMock(status_code=0)
            fn = MagicMock(return_value=MagicMock(status=MagicMock(statusCode=0)))
            req = MagicMock()
            client = HiveServerClient(MagicMock(), MagicMock())
            assert_raises(Exception, client.call, fn, req, status=None)

            get_n_sessions.return_value = [MagicMock()]
            (res, session1) = client.call(fn, req, status=None)
            open_session.assert_called_once()
    finally:
      for f in finish:
        f()