# Copyright (c) 2018 VMware Inc
# Copyright 2016 NTT All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_log import log as logging
from tempest import config
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions

from congress_tempest_plugin.tests.scenario import helper
from congress_tempest_plugin.tests.scenario import manager_congress


CONF = config.CONF
LOG = logging.getLogger(__name__)

DS_NAME = 'vitrage'
DRIVER_NAME = 'vitrage'
TEST_PAYLOAD_ACTIVATE = {
    "notification": "vitrage.alarm.activate",
    "payload": {
        "vitrage_id": "2def31e9-6d9f-4c16-b007-893caa806cd4",
        "resource": {
            "vitrage_id": "437f1f4c-ccce-40a4-ac62-1c2f1fd9f6ac",
            "name": "app-1-server-1-jz6qvznkmnif",
            "update_timestamp": "2018-01-22 10:00:34.327142+00:00",
            "vitrage_category": "RESOURCE",
            "vitrage_operational_state": "OK",
            "vitrage_type": "nova.instance",
            "project_id": "8f007e5ba0944e84baa6f2a4f2b5d03a",
            "id": "9b7d93b9-94ec-41e1-9cec-f28d4f8d702c"},
        "update_timestamp": "2018-01-22T10:00:34Z",
        "vitrage_category": "ALARM",
        "state": "Active",
        "vitrage_type": "vitrage",
        "vitrage_operational_severity": "WARNING",
        "name": "Instance memory performance degraded"}}
TEST_PAYLOAD_DEACTIVATE = {
    "notification": "vitrage.alarm.deactivate",
    "payload": {
        "vitrage_id": "2def31e9-6d9f-4c16-b007-893caa806cd4",
        "resource": {
            "vitrage_id": "437f1f4c-ccce-40a4-ac62-1c2f1fd9f6ac",
            "name": "app-1-server-1-jz6qvznkmnif",
            "update_timestamp": "2018-01-22 11:00:34.327142+00:00",
            "vitrage_category": "RESOURCE",
            "vitrage_operational_state": "OK",
            "vitrage_type": "nova.instance",
            "project_id": "8f007e5ba0944e84baa6f2a4f2b5d03a",
            "id": "9b7d93b9-94ec-41e1-9cec-f28d4f8d702c"},
        "update_timestamp": "2018-01-22T11:00:34Z",
        "vitrage_category": "ALARM",
        "state": "Inactive",
        "vitrage_type": "vitrage",
        "vitrage_operational_severity": "OK",
        "name": "Instance memory performance degraded"}}


class TestVitrageDriver(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestVitrageDriver, cls).skip_checks()
        if not CONF.congress_feature_enabled.vitrage_webhook:
            msg = ("feature not available in this congress version")
            raise cls.skipException(msg)

    def setUp(self):
        super(TestVitrageDriver, self).setUp()
        vitrage_setting = {
            'name': DS_NAME,
            'driver': DRIVER_NAME,
            'config': None,
            }
        self.client = self.os_admin.congress_client

        response = self.client.create_datasource(vitrage_setting)
        self.datasource_id = response['id']

        # Check if service is up
        @helper.retry_on_exception
        def _check_service():
            self.client.list_datasource_status(self.datasource_id)
            return True

        if not test_utils.call_until_true(func=_check_service,
                                          duration=60, sleep_for=1):
            raise exceptions.TimeoutException(
                "Vitrage data source service is not up")

    def tearDown(self):
        super(TestVitrageDriver, self).tearDown()
        self.client.delete_datasource(self.datasource_id)

    def _list_datasource_rows(self, datasource, table):
        return self.client.list_datasource_rows(datasource, table)

    @decorators.attr(type='smoke')
    def test_vitrage_alarms_table(self):
        self.client.send_datasource_webhook(
            self.datasource_id, TEST_PAYLOAD_ACTIVATE)
        results = self._list_datasource_rows(self.datasource_id, 'alarms')
        if len(results['results']) != 1:
            error_msg = ('Unexpected additional rows are '
                         'inserted. row details: %s' % results['results'])
            raise exceptions.InvalidStructure(error_msg)

        expected_row = [u'Instance memory performance degraded',
                        u'Active',
                        u'vitrage',
                        u'WARNING',
                        u'2def31e9-6d9f-4c16-b007-893caa806cd4',
                        u'2018-01-22T10:00:34Z',
                        results['results'][0]['data'][6],
                        u'app-1-server-1-jz6qvznkmnif',
                        u'9b7d93b9-94ec-41e1-9cec-f28d4f8d702c',
                        u'437f1f4c-ccce-40a4-ac62-1c2f1fd9f6ac',
                        u'8f007e5ba0944e84baa6f2a4f2b5d03a',
                        u'OK',
                        u'nova.instance']

        if results['results'][0]['data'] != expected_row:
            msg = ('inserted row %s is not expected row %s'
                   % (results['results'][0]['data'], expected_row))
            raise exceptions.InvalidStructure(msg)

        self.client.send_datasource_webhook(
            self.datasource_id, TEST_PAYLOAD_DEACTIVATE)
        results = self._list_datasource_rows(self.datasource_id, 'alarms')
        if len(results['results']) != 1:
            error_msg = ('Unexpected additional rows are '
                         'inserted. row details: %s' % results['results'])
            raise exceptions.InvalidStructure(error_msg)

        expected_row = [u'Instance memory performance degraded',
                        u'Inactive',
                        u'vitrage',
                        u'OK',
                        u'2def31e9-6d9f-4c16-b007-893caa806cd4',
                        u'2018-01-22T11:00:34Z',
                        results['results'][0]['data'][6],
                        u'app-1-server-1-jz6qvznkmnif',
                        u'9b7d93b9-94ec-41e1-9cec-f28d4f8d702c',
                        u'437f1f4c-ccce-40a4-ac62-1c2f1fd9f6ac',
                        u'8f007e5ba0944e84baa6f2a4f2b5d03a',
                        u'OK',
                        u'nova.instance']

        if results['results'][0]['data'] != expected_row:
            msg = ('inserted row %s is not expected row %s'
                   % (results['results'][0]['data'], expected_row))
            raise exceptions.InvalidStructure(msg)

    @decorators.attr(type='smoke')
    def test_vitrage_alarms_table_subscribe_then_publish(self):
        policy_name = self._create_random_policy('vitrage')
        policy_rule = 'test(name) :- {}:alarms(name=name)'.format(DS_NAME)
        self._create_policy_rule_retry(policy_name, policy_rule)

        self.client.send_datasource_webhook(
            self.datasource_id, TEST_PAYLOAD_ACTIVATE)

        @helper.retry_on_exception
        def _check_policy_eval():
            rows = self.client.list_policy_rows(policy_name, 'test')['results']
            if len(rows) < 1:
                LOG.debug('Too few rows: %s', rows)
                return False
            elif len(rows) > 1:
                LOG.debug('Too many rows: %s', rows)
                return False
            elif rows[0]['data'] != ['Instance memory performance degraded']:
                LOG.debug('Incorrect row data: %s', rows[0]['data'])
                return False
            return True

        if not test_utils.call_until_true(func=_check_policy_eval,
                                          duration=10, sleep_for=1):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    @decorators.attr(type='smoke')
    def test_vitrage_alarms_table_publish_then_subscribe(self):
        self.client.send_datasource_webhook(
            self.datasource_id, TEST_PAYLOAD_ACTIVATE)
        policy_name = self._create_random_policy('vitrage')
        policy_rule = 'test(name) :- {}:alarms(name=name)'.format(DS_NAME)
        self._create_policy_rule_retry(policy_name, policy_rule)

        @helper.retry_on_exception
        def _check_policy_eval():
            rows = self.client.list_policy_rows(policy_name, 'test')['results']
            if len(rows) < 1:
                LOG.debug('Too few rows: %s', rows)
                return False
            elif len(rows) > 1:
                LOG.debug('Too many rows: %s', rows)
                return False
            elif rows[0]['data'] != ['Instance memory performance degraded']:
                LOG.debug('Incorrect row data: %s', rows[0]['data'])
                return False
            return True

        if not test_utils.call_until_true(func=_check_policy_eval,
                                          duration=10, sleep_for=1):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")
