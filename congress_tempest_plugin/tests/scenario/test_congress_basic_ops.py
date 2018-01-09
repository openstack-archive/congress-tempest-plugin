# Copyright 2012 OpenStack Foundation
# Copyright 2013 Hewlett-Packard Development Company, L.P.
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

import time

from tempest.common import utils
from tempest import config
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions

from congress_tempest_plugin.tests.scenario import helper
from congress_tempest_plugin.tests.scenario import manager_congress


CONF = config.CONF


class TestPolicyBasicOps(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestPolicyBasicOps, cls).skip_checks()
        if not (CONF.network.project_networks_reachable
                or CONF.network.public_network_id):
            msg = ('Either project_networks_reachable must be "true", or '
                   'public_network_id must be defined.')
            cls.enabled = False
            raise cls.skipException(msg)

    def setUp(self):
        super(TestPolicyBasicOps, self).setUp()
        self.keypairs = {}
        self.servers = []

    def _create_test_server(self, name=None):
        image_ref = CONF.compute.image_ref
        flavor_ref = CONF.compute.flavor_ref
        keypair = self.create_keypair()
        security_group = self._create_security_group()
        security_groups = [{'name': security_group['name']}]
        create_kwargs = {'key_name': keypair['name'],
                         'security_groups': security_groups}
        instance = self.create_server(name=name,
                                      image_id=image_ref,
                                      flavor=flavor_ref,
                                      wait_until='ACTIVE',
                                      **create_kwargs)
        return instance

    @decorators.attr(type='smoke')
    @utils.services('compute', 'network')
    def test_execution_action(self):
        metadata = {'testkey1': 'value3'}
        res = {'meta': {'testkey1': 'value3'}}
        server = self._create_test_server()
        congress_client = self.os_admin.congress_client
        servers_client = self.os_admin.servers_client
        policy = self._create_random_policy()
        service = 'nova'
        action = 'servers.set_meta'
        action_args = {'args': {'positional': [],
                                'named': {'server': server['id'],
                                          'metadata': metadata}}}
        body = action_args

        f = lambda: servers_client.show_server_metadata_item(server['id'],
                                                             'testkey1')
        # execute via datasource api
        body.update({'name': action})
        congress_client.execute_datasource_action(service, "execute", body)
        helper.retry_check_function_return_value(f, res)

        # execute via policy api
        body.update({'name': service + ':' + action})
        congress_client.execute_policy_action(policy, "execute", False,
                                              False, body)
        helper.retry_check_function_return_value(f, res)

    @decorators.attr(type='smoke')
    @utils.services('compute', 'network')
    def test_policy_basic_op(self):
        self._setup_network_and_servers()
        body = {"rule": "port_security_group(id, security_group_name) "
                        ":-neutronv2:ports(id, tenant_id, name, network_id,"
                        "mac_address, admin_state_up, status, device_id, "
                        "device_owner),"
                        "neutronv2:security_group_port_bindings(id, "
                        "security_group_id), neutronv2:security_groups("
                        "security_group_id, tenant_id1, security_group_name,"
                        "description)"}
        results = self.os_admin.congress_client.create_policy_rule(
            'classification', body)
        rule_id = results['id']
        self.addCleanup(
            self.os_admin.congress_client.delete_policy_rule,
            'classification', rule_id)

        # Find the ports of on this server
        ports = self.os_admin.ports_client.list_ports(
            device_id=self.servers[0]['id'])['ports']

        def check_data():
            results = self.os_admin.congress_client.list_policy_rows(
                'classification', 'port_security_group')
            for row in results['results']:
                if (row['data'][0] == ports[0]['id'] and
                    row['data'][1] ==
                        self.servers[0]['security_groups'][0]['name']):
                        return True
            else:
                return False

        time.sleep(65)  # sleep for replicated PE sync
        # Note(ekcs): do not use retry because we want to make sure the call
        # succeeds on the first try after adequate time.
        # If retry used, it may pass based on succeding on one replica but
        # failing on all others.
        self.assertTrue(check_data(),
                        "Data did not converge in time or failure in server")

    @decorators.attr(type='smoke')
    @utils.services('compute', 'network')
    def test_reactive_enforcement(self):
        servers_client = self.os_admin.servers_client
        server_name = 'server_under_test'
        server = self._create_test_server(name=server_name)
        policy_name = self._create_random_policy()
        meta_key = 'meta_test_key1'
        meta_val = 'value1'
        meta_data = {'meta': {meta_key: meta_val}}
        rules = [
            'execute[nova:servers_set_meta(id, "%s", "%s")] :- '
            'test_servers(id)' % (meta_key, meta_val),
            'test_servers(id) :- '
            'nova:servers(id, name, host_id, status, tenant_id,'
            'user_id, image_id, flavor_id, zone, host_name),'
            'equal(name, "%s")' % server_name]

        for rule in rules:
            self._create_policy_rule(policy_name, rule)
        f = lambda: servers_client.show_server_metadata_item(server['id'],
                                                             meta_key)
        time.sleep(80)  # sleep for replicated PE sync
        # Note: seems reactive enforcement takes a bit longer
        # succeeds on the first try after adequate time.
        # If retry used, it may pass based on succeding on one replica but
        # failing on all others.
        self.assertEqual(f(), meta_data)


class TestPolicyLibraryBasicOps(manager_congress.ScenarioPolicyBase):
    @decorators.attr(type='smoke')
    def test_policy_library_basic_op(self):
        response = self.os_admin.congress_client.list_library_policy()
        initial_state = response['results']

        self.assertGreater(
            len(initial_state), 0, 'library policy shows no policies, '
                                   'indicating failed load-on-startup.')

        test_policy = {
            "name": "test_policy",
            "description": "test policy description",
            "kind": "nonrecursive",
            "abbreviation": "abbr",
            "rules": [{"rule": "p(x) :- q(x)", "comment": "test comment",
                       "name": "test name"},
                      {"rule": "p(x) :- q2(x)", "comment": "test comment2",
                       "name": "test name2"}]
        }
        response = self.os_admin.congress_client.create_library_policy(
            test_policy)
        policy_id = response['id']
        test_policy['id'] = policy_id

        def delete_if_found(id_):
            try:
                self.os_admin.congress_client.delete_library_policy(id_)
            except exceptions.NotFound:
                pass

        self.addCleanup(delete_if_found, policy_id)

        response = self.os_admin.congress_client.list_library_policy()
        new_state = response['results']

        self.assertEqual(len(initial_state) + 1, len(new_state),
                         'new library policy not reflected in list results')
        self.assertIn(test_policy, new_state,
                      'new library policy not reflected in list results')

        self.os_admin.congress_client.delete_library_policy(policy_id)

        response = self.os_admin.congress_client.list_library_policy()
        new_state = response['results']

        self.assertEqual(len(initial_state), len(new_state),
                         'library policy delete not reflected in list results')
        self.assertNotIn(test_policy, new_state,
                         'library policy delete not reflected in list results')

    @decorators.attr(type='smoke')
    def test_create_library_policies(self):
        '''test the library policies by loading into policy engine'''

        # list library policies (by name) to skip in this test, perhaps
        # because it depends on datasources not available in gate
        skip_names_list = []

        response = self.os_admin.congress_client.list_library_policy()
        library_policies = response['results']

        for library_policy in library_policies:
            if library_policy['name'] not in skip_names_list:
                resp = self.os_admin.congress_client.create_policy(
                    body=None, params={'library_policy': library_policy['id']})
                self.assertEqual(resp.response['status'], '201',
                                 'Policy activation failed')
                self.addCleanup(self.os_admin.congress_client.delete_policy,
                                resp['id'])


class TestCongressDataSources(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestCongressDataSources, cls).skip_checks()
        if not (CONF.network.project_networks_reachable
                or CONF.network.public_network_id):
            msg = ('Either project_networks_reachable must be "true", or '
                   'public_network_id must be defined.')
            cls.enabled = False
            raise cls.skipException(msg)

    def test_all_loaded_datasources_are_initialized(self):

        @helper.retry_on_exception
        def _check_all_datasources_are_initialized():
            datasources = self.os_admin.congress_client.list_datasources()
            for datasource in datasources['results']:
                results = (
                    self.os_admin.congress_client.list_datasource_status(
                        datasource['id']))
                if results['initialized'] != 'True':
                    return False
            return True

        if not test_utils.call_until_true(
            func=_check_all_datasources_are_initialized,
                duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    def test_all_datasources_have_tables(self):

        @helper.retry_on_exception
        def check_data():
            datasources = self.os_admin.congress_client.list_datasources()
            for datasource in datasources['results']:
                results = (
                    self.os_admin.congress_client.list_datasource_tables(
                        datasource['id']))
                # NOTE(arosen): if there are no results here we return false as
                # there is something wrong with a driver as it doesn't expose
                # any tables.
                if not results['results']:
                    return False
            return True

        if not test_utils.call_until_true(func=check_data,
                                          duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")
