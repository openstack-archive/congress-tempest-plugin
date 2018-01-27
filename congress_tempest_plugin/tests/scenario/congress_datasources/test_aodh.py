# Copyright 2016 NEC Corporation. All rights reserved.
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

from tempest import config
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions

from congress_tempest_plugin.tests.scenario import manager_congress


CONF = config.CONF


class TestAodhDriver(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestAodhDriver, cls).skip_checks()
        if not getattr(CONF.service_available, 'aodh', False):
            msg = ("%s skipped as aodh is not available" %
                   cls.__class__.__name__)
            raise cls.skipException(msg)

    def setUp(self):
        super(TestAodhDriver, self).setUp()
        self.alarms_client = self.os_admin.alarms_client
        self.datasource_id = manager_congress.get_datasource_id(
            self.os_admin.congress_client, 'aodh')

    @decorators.attr(type='smoke')
    def test_aodh_alarms_table(self):
        self.alarms_client.create_alarm(
            name='test-alarm',
            enabled=False,
            type='event',
            event_rule={})

        alarms_schema = (
            self.os_admin.congress_client.show_datasource_table_schema(
                self.datasource_id, 'alarms')['columns'])
        alarms_id_col = next(i for i, c in enumerate(alarms_schema)
                             if c['name'] == 'alarm_id')

        def _check_data_table_aodh_alarms():
            # Fetch data from aodh each time, because this test may start
            # before aodh has all the users.
            alarms = self.alarms_client.list_alarms()
            alarm_map = {}
            for alarm in alarms:
                alarm_map[alarm['alarm_id']] = alarm

            results = (
                self.os_admin.congress_client.list_datasource_rows(
                    self.datasource_id, 'alarms'))

            for row in results['results']:
                try:
                    alarm_row = alarm_map[row['data'][alarms_id_col]]
                except KeyError:
                    return False
                for index in range(len(alarms_schema)):
                    if (str(row['data'][index]) !=
                            str(alarm_row[alarms_schema[index]['name']])):
                        return False
            return True

        if not test_utils.call_until_true(func=_check_data_table_aodh_alarms,
                                          duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    @decorators.attr(type='smoke')
    def test_update_no_error(self):
        if not test_utils.call_until_true(
                func=lambda: self.check_datasource_no_error('aodh'),
                duration=30, sleep_for=5):
            raise exceptions.TimeoutException('Datasource could not poll '
                                              'without error.')
