# Copyright 2017 VMware Corporation. All rights reserved.
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
from oslo_log import log as logging
from tempest import config
from tempest.lib import decorators

from congress_tempest_plugin.tests.scenario import manager_congress


CONF = config.CONF
LOG = logging.getLogger(__name__)


class TestMistralDriver(manager_congress.DatasourceDriverTestBase):

    @classmethod
    def skip_checks(cls):
        super(TestMistralDriver, cls).skip_checks()
        if not getattr(CONF.service_available, 'mistral', False):
            msg = ("%s skipped because mistral service is not configured" %
                   cls.__class__.__name__)
            raise cls.skipException(msg)

    def setUp(self):
        super(TestMistralDriver, self).setUp()
        self.datasource_name = 'mistral'
        self.datasource_id = manager_congress.get_datasource_id(
            self.os_admin.congress_client, self.datasource_name)

    @decorators.attr(type='smoke')
    def test_mistral_workflows_table(self):
        table_name = 'workflows'
        service_data_fetch_func = (
            lambda: self.os_admin.mistral_client.get_list_obj(
                'workflows')[1]['workflows'])
        self.check_service_data_against_congress_table(
            table_name, service_data_fetch_func,
            missing_attributes_allowed=['description', 'updated_at'])

    @decorators.attr(type='smoke')
    def test_mistral_actions_table(self):
        table_name = 'actions'
        service_data_fetch_func = (
            lambda: self.os_admin.mistral_client.get_list_obj(
                'actions')[1]['actions'])
        self.check_service_data_against_congress_table(
            table_name, service_data_fetch_func)

    # FIXME(ekcs): enable when we figure out how to use admin project in
    # tempest test setup to populate executions with dummy data.
    # @decorators.attr(type='smoke')
    # def test_mistral_workflow_executions_table(self):
    #     table_name = 'workflow_executions'
    #     service_data_fetch_func = lambda: self.service_client.get_list_obj(
    #         'executions')[1]['executions']
    #     self.check_service_data_against_congress_table(
    #         table_name, service_data_fetch_func)
    #
    # @decorators.attr(type='smoke')
    # def test_mistral_action_executions_table(self):
    #     table_name = 'action_executions'
    #     service_data_fetch_func = lambda: self.service_client.get_list_obj(
    #         'action_executions')[1]['action_executions']
    #     self.check_service_data_against_congress_table(
    #         table_name, service_data_fetch_func)
