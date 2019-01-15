# Copyright 2018 VMware Corporation. NEC, Inc. All rights reserved.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import testtools

from tempest import config
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions

from congress_tempest_plugin.tests.scenario import helper
from congress_tempest_plugin.tests.scenario import manager_congress


CONF = config.CONF
DRIVER_NAME = 'monasca'


class TestMonascaDriver(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestMonascaDriver, cls).skip_checks()
        if not getattr(CONF.service_available, DRIVER_NAME, False):
            msg = ("%s skipped because %s service is not configured" %
                   (cls.__class__.__name__, DRIVER_NAME))
            raise cls.skipException(msg)

    # TODO(testing): checks on correctness of data in updates

    @decorators.attr(type='smoke')
    def test_update_no_error(self):
        if not test_utils.call_until_true(
                func=lambda: self.check_datasource_no_error(DRIVER_NAME),
                duration=30, sleep_for=5):
            raise exceptions.TimeoutException('Datasource could not poll '
                                              'without error.')


class TestMonascaWebhookDriver(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestMonascaWebhookDriver, cls).skip_checks()
        if not CONF.congress_feature_enabled.monasca_webhook:
            msg = ("feature not available in this congress version")
            raise cls.skipException(msg)

    def setUp(self):
        super(TestMonascaWebhookDriver, self).setUp()
        monasca_setting = {
            'name': 'monasca_webhook',
            'driver': 'monasca_webhook',
            'config': None,
            }
        self.client = self.os_admin.congress_client

        response = self.client.create_datasource(monasca_setting)
        self.datasource_id = response['id']

    def tearDown(self):
        super(TestMonascaWebhookDriver, self).tearDown()
        self.client.delete_datasource(self.datasource_id)

    def _list_datasource_rows(self, datasource, table):
        return self.client.list_datasource_rows(datasource, table)

    @decorators.attr(type='smoke')
    @testtools.skipIf(CONF.congress_feature_enabled.monasca_webhook_rocky,
                      'Test expects new (post-Rocky) monasca webhook schema.')
    def test_monasca_alarm_notification_table(self):
        test_alarm = {
            'metrics': [
                {u'dimensions': {u'hostname': u'openstack-13.local.lan',
                                 u'service': u'monitoring'},
                 u'id': None,
                 u'name': u'load.avg_1_min'}],
            'alarm_id': u'3beb4934-053d-4f8f-9704-273bffc244',
            'state': u'ALARM',
            'alarm_timestamp': 1531821822,
            'tenant_id': u'3661888238874df098988deab07c599d',
            'old_state': u'UNDETERMINED',
            'alarm_description': u'',
            'message': u'Thresholds were exceeded for alarm',
            'alarm_definition_id': u'8e5d033f-28cc-459f-91d4-813307e4ca',
            'alarm_name': u'alarmPerHost23'}

        # Check if service is up
        @helper.retry_on_exception
        def _check_service():
            self.client.list_datasource_status(self.datasource_id)
            return True

        if not test_utils.call_until_true(func=_check_service,
                                          duration=60, sleep_for=1):
            raise exceptions.TimeoutException(
                "Monasca-Webhook data source service is not up")

        def _check_result_for_exception(result, expected_result,
                                        result_length=1):
            if len(result['results']) != result_length:
                error_msg = ('Unexpected number of rows are '
                             'inserted. Row details: %s' % result['results'])
                raise exceptions.InvalidStructure(error_msg)

            output = []
            for data in result['results']:
                output.append(data['data'])
            output = sorted(output)
            expected_result = sorted(expected_result)
            for index in range(result_length):
                if output[index] != expected_result[index]:
                    msg = ('inserted row %s is not expected row %s'
                           % (output[index], expected_result[index]))
                    raise exceptions.InvalidStructure(msg)

        self.client.send_datasource_webhook(self.datasource_id, test_alarm)
        alarm_notification = self._list_datasource_rows(self.datasource_id,
                                                        'alarm_notification')

        expected_alarm_notification = [[u'3beb4934-053d-4f8f-9704-273bffc244',
                                        u'8e5d033f-28cc-459f-91d4-813307e4ca',
                                        u'alarmPerHost23',
                                        u'',
                                        1531821822,
                                        u'ALARM',
                                        u'UNDETERMINED',
                                        u'Thresholds were exceeded for alarm',
                                        u'3661888238874df098988deab07c599d']]

        _check_result_for_exception(alarm_notification,
                                    expected_alarm_notification)

        metrics_result = self._list_datasource_rows(self.datasource_id,
                                                    'alarms.metrics')
        dimension_id = metrics_result['results'][0]['data'][3]
        expected_metrics = [[u'3beb4934-053d-4f8f-9704-273bffc244',
                             u'None',
                             u'load.avg_1_min',
                             dimension_id]]
        _check_result_for_exception(metrics_result, expected_metrics)

        dimension_result = self._list_datasource_rows(
            self.datasource_id, 'alarms.metrics.dimensions')
        expected_dimensions = [
            [dimension_id, u'hostname', u'openstack-13.local.lan'],
            [dimension_id, u'service', u'monitoring']]
        _check_result_for_exception(dimension_result, expected_dimensions, 2)

    @decorators.attr(type='smoke')
    @testtools.skipUnless(CONF.congress_feature_enabled.monasca_webhook_rocky,
                          'Test expects monasca webhook rocky schema.')
    def test_monasca_alarm_notification_table_rocky(self):
        test_alarm = {
            'metrics': [
                {u'dimensions': {u'hostname': u'openstack-13.local.lan',
                                 u'service': u'monitoring'},
                 u'id': None,
                 u'name': u'load.avg_1_min'}],
            'alarm_id': u'3beb4934-053d-4f8f-9704-273bffc2441b',
            'state': u'ALARM',
            'alarm_timestamp': 1531821822,
            'tenant_id': u'3661888238874df098988deab07c599d',
            'old_state': u'UNDETERMINED',
            'alarm_description': u'',
            'message': u'Thresholds were exceeded for the sub-alarms',
            'alarm_definition_id': u'8e5d033f-28cc-459f-91d4-813307e4ca8a',
            'alarm_name': u'alarmPerHost23'}

        # Check if service is up
        @helper.retry_on_exception
        def _check_service():
            self.client.list_datasource_status(self.datasource_id)
            return True

        if not test_utils.call_until_true(func=_check_service,
                                          duration=60, sleep_for=1):
            raise exceptions.TimeoutException(
                "Monasca-Webhook data source service is not up")

        self.client.send_datasource_webhook(self.datasource_id, test_alarm)
        results = self._list_datasource_rows(self.datasource_id,
                                             'alarm_notification')
        if len(results['results']) != 1:
            error_msg = ('Unexpected additional rows are '
                         'inserted. row details: %s' % results['results'])
            raise exceptions.InvalidStructure(error_msg)

        expected_row = [u'3beb4934-053d-4f8f-9704-273bffc2441b',
                        u'8e5d033f-28cc-459f-91d4-813307e4ca8a',
                        u'alarmPerHost23',
                        u'',
                        1531821822,
                        u'ALARM',
                        u'UNDETERMINED',
                        u'Thresholds were exceeded for the sub-alarms',
                        u'3661888238874df098988deab07c599d',
                        u'None',
                        u'load.avg_1_min',
                        u'openstack-13.local.lan',
                        u'monitoring']

        if results['results'][0]['data'] != expected_row:
            msg = ('inserted row %s is not expected row %s'
                   % (results['results'][0]['data'], expected_row))
            raise exceptions.InvalidStructure(msg)
