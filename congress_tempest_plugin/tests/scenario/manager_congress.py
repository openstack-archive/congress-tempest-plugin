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

import collections
import random
import re
import string

from oslo_log import log as logging
from tempest.common import credentials_factory as credentials
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions
from tempest import manager as tempestmanager

from congress_tempest_plugin.services.congress_network import qos_client
from congress_tempest_plugin.services.congress_network import qos_rule_client
from congress_tempest_plugin.services.policy import policy_client
# use local copy of tempest scenario manager during upstream refactoring
from congress_tempest_plugin.tests.scenario import helper
from congress_tempest_plugin.tests.scenario import manager

CONF = config.CONF
LOG = logging.getLogger(__name__)

Floating_IP_tuple = collections.namedtuple('Floating_IP_tuple',
                                           ['floating_ip', 'server'])


def get_datasource_id(client, name):
    datasources = client.list_datasources()
    for datasource in datasources['results']:
        if datasource['name'] == name:
            return datasource['id']
    raise Exception("Datasource %s not found." % name)


# Note: these tests all use neutron today so we mix with that.
class ScenarioPolicyBase(manager.NetworkScenarioTest):
    @classmethod
    def setUpClass(cls):
        super(ScenarioPolicyBase, cls).setUpClass()
        # auth provider for admin credentials
        creds = credentials.get_configured_admin_credentials('identity_admin')
        auth_prov = tempestmanager.get_auth_provider(creds)
        cls.setup_required_clients(auth_prov)

    @classmethod
    def setup_required_clients(cls, auth_prov):
        # Get congress client
        cls.os_admin.congress_client = policy_client.PolicyClient(
            auth_prov, "policy", CONF.identity.region)

        cls.os_admin.qos_client = qos_client.QosPoliciesClient(
            auth_prov, "network", CONF.identity.region)

        cls.os_admin.qos_rule_client = qos_rule_client.QosRuleClient(
            auth_prov, "network", CONF.identity.region)

        # Get alarms client
        if getattr(CONF.service_available, 'aodh', False):
            import telemetry_tempest_plugin.aodh.service.client as alarm_client
            cls.os_admin.alarms_client = (
                alarm_client.AlarmingClient(
                    auth_prov,
                    CONF.alarming_plugin.catalog_type, CONF.identity.region,
                    CONF.alarming_plugin.endpoint_type))

        # Get mistral client
        if getattr(CONF.service_available, 'mistral', False):
            import mistral_tempest_tests.services.\
                v2.mistral_client as mistral_client
            cls.os_admin.mistral_client = mistral_client.MistralClientV2(
                auth_prov, 'workflowv2')

    def _setup_network_and_servers(self):
        self.security_group = self._create_security_group()
        self.network, self.subnet, self.router = self.create_networks()
        self.check_networks()

        name = data_utils.rand_name('server-smoke')
        server = self._create_server(name, self.network)
        self._check_tenant_network_connectivity()

        floating_ip = self.create_floating_ip(server)
        self.floating_ip_tuple = Floating_IP_tuple(floating_ip, server)

    def check_networks(self):
        """Check for newly created network/subnet/router.

        Checks that we see the newly created network/subnet/router via
        checking the result of list_[networks,routers,subnets].
        """

        seen_nets = self.os_admin.networks_client.list_networks()
        seen_names = [n['name'] for n in seen_nets['networks']]
        seen_ids = [n['id'] for n in seen_nets['networks']]
        self.assertIn(self.network['name'], seen_names)
        self.assertIn(self.network['id'], seen_ids)

        if self.subnet:
            seen_subnets = self.os_admin.subnets_client.list_subnets()
            seen_net_ids = [n['network_id'] for n in seen_subnets['subnets']]
            seen_subnet_ids = [n['id'] for n in seen_subnets['subnets']]
            self.assertIn(self.network['id'], seen_net_ids)
            self.assertIn(self.subnet['id'], seen_subnet_ids)

        if self.router:
            seen_routers = self.os_admin.routers_client.list_routers()
            seen_router_ids = [n['id'] for n in seen_routers['routers']]
            seen_router_names = [n['name'] for n in seen_routers['routers']]
            self.assertIn(self.router['name'],
                          seen_router_names)
            self.assertIn(self.router['id'],
                          seen_router_ids)

    def check_datasource_no_error(self, datasource_name):
        """Check that datasource has no error on latest update"""
        ds_status = self.os_admin.congress_client.list_datasource_status(
            datasource_name)
        if (ds_status['initialized'] == 'True' and
           ds_status['number_of_updates'] != '0' and
           ds_status['last_error'] == 'None'):
            return True
        else:
            LOG.debug('datasource %s not initialized, not polled, or shows '
                      'error. Full status: %s', datasource_name, ds_status)
            return False

    def _create_server(self, name, network):
        keypair = self.create_keypair()
        self.keypairs[keypair['name']] = keypair
        security_groups = [{'name': self.security_group['name']}]
        create_kwargs = {
            'networks': [
                {'uuid': network['id']},
            ],
            'key_name': keypair['name'],
            'security_groups': security_groups,
        }
        server = self.create_server(name=name, wait_until='ACTIVE',
                                    **create_kwargs)
        self.servers.append(server)
        return server

    def _get_server_key(self, server):
        return self.keypairs[server['key_name']]['private_key']

    def _check_tenant_network_connectivity(self):
        ssh_login = CONF.validation.image_ssh_user
        for server in self.servers:
            # call the common method in the parent class
            super(ScenarioPolicyBase, self)._check_tenant_network_connectivity(
                server, ssh_login, self._get_server_key(server),
                servers_for_debug=self.servers)

    def _create_and_associate_floating_ips(self, server):
        public_network_id = CONF.network.public_network_id
        floating_ip = self._create_floating_ip(server, public_network_id)
        self.floating_ip_tuple = Floating_IP_tuple(floating_ip, server)

    def _check_public_network_connectivity(self, should_connect=True,
                                           msg=None):
        ssh_login = CONF.compute.image_ssh_user
        floating_ip, server = self.floating_ip_tuple
        ip_address = floating_ip.floating_ip_address
        private_key = None
        if should_connect:
            private_key = self._get_server_key(server)
        # call the common method in the parent class
        super(ScenarioPolicyBase, self)._check_public_network_connectivity(
            ip_address, ssh_login, private_key, should_connect, msg,
            self.servers)

    def _disassociate_floating_ips(self):
        floating_ip, server = self.floating_ip_tuple
        self._disassociate_floating_ip(floating_ip)
        self.floating_ip_tuple = Floating_IP_tuple(
            floating_ip, None)

    def _reassociate_floating_ips(self):
        floating_ip, server = self.floating_ip_tuple
        name = data_utils.rand_name('new_server-smoke-')
        # create a new server for the floating ip
        server = self._create_server(name, self.network)
        self._associate_floating_ip(floating_ip, server)
        self.floating_ip_tuple = Floating_IP_tuple(
            floating_ip, server)

    def _create_new_network(self):
        self.new_net = self._create_network(tenant_id=self.tenant_id)
        self.new_subnet = self._create_subnet(
            network=self.new_net,
            gateway_ip=None)

    def _get_server_nics(self, ssh_client):
        reg = re.compile(r'(?P<num>\d+): (?P<nic_name>\w+):')
        ipatxt = ssh_client.exec_command("ip address")
        return reg.findall(ipatxt)

    def _check_network_internal_connectivity(self, network):
        """via ssh check VM internal connectivity:

        - ping internal gateway and DHCP port, implying in-tenant connectivity
        pinging both, because L3 and DHCP agents might be on different nodes.
        """
        floating_ip, server = self.floating_ip_tuple
        # get internal ports' ips:
        # get all network ports in the new network
        ports = self.os_admin.ports_client.list_ports(
            tenant_id=server['tenant_id'], network_id=network.id)['ports']

        internal_ips = (p['fixed_ips'][0]['ip_address'] for p in ports
                        if p['device_owner'].startswith('network'))

        self._check_server_connectivity(floating_ip, internal_ips)

    def _check_network_external_connectivity(self):
        """ping public network default gateway to imply external conn."""
        if not CONF.network.public_network_id:
            msg = 'public network not defined.'
            LOG.info(msg)
            return

        subnet = self.os_admin.subnets_client.list_subnets(
            network_id=CONF.network.public_network_id)['subnets']
        self.assertEqual(1, len(subnet), "Found %d subnets" % len(subnet))

        external_ips = [subnet[0]['gateway_ip']]
        self._check_server_connectivity(self.floating_ip_tuple.floating_ip,
                                        external_ips)

    def _check_server_connectivity(self, floating_ip, address_list):
        ip_address = floating_ip.floating_ip_address
        private_key = self._get_server_key(self.floating_ip_tuple.server)
        ssh_source = self._ssh_to_server(ip_address, private_key)

        for remote_ip in address_list:
            try:
                self.assertTrue(self._check_remote_connectivity(ssh_source,
                                                                remote_ip),
                                "Timed out waiting for %s to become "
                                "reachable" % remote_ip)
            except Exception:
                LOG.exception("Unable to access {dest} via ssh to "
                              "floating-ip {src}".format(dest=remote_ip,
                                                         src=floating_ip))
                raise

    def _create_random_policy(self, prefix='nova'):
        policy_name = prefix + "_%s" % ''.join(
            random.choice(string.ascii_lowercase) for x in range(10))
        body = {"name": policy_name}
        resp = self.os_admin.congress_client.create_policy(body)
        self.addCleanup(self.os_admin.congress_client.delete_policy,
                        resp['id'])
        return resp['name']

    def _create_policy_rule(self, policy_name, rule, rule_name=None,
                            comment=None):
        body = {'rule': rule}
        if rule_name:
            body['name'] = rule_name
        if comment:
            body['comment'] = comment
        client = self.os_admin.congress_client
        response = client.create_policy_rule(policy_name, body)
        if response:
            self.addCleanup(client.delete_policy_rule, policy_name,
                            response['id'])
            return response
        else:
            raise Exception('Failed to create policy rule (%s, %s)'
                            % (policy_name, rule))

    def _create_policy_rule_retry(
            self, policy_name, rule, rule_name=None, comment=None):
        return helper.retry_check_function_return_value_condition(
            lambda: self._create_policy_rule(
                policy_name, rule, rule_name, comment),
            lambda v: True, retry_attempts=50, retry_interval=2)


class DatasourceDriverTestBase(ScenarioPolicyBase):

    def check_service_data_against_congress_table(
            self, table_name, service_data_fetch_func, check_nonempty=True,
            missing_attributes_allowed=None):
        if missing_attributes_allowed is None:
            missing_attributes_allowed = []
        table_schema = (
            self.os_admin.congress_client.show_datasource_table_schema(
                self.datasource_id, table_name)['columns'])
        table_id_col = next(i for i, c in enumerate(table_schema)
                            if c['name'] == 'id')

        def _check_data():
            # Fetch data each time, because test may go before service has data
            service_data = service_data_fetch_func()

            if check_nonempty and len(service_data) == 0:
                LOG.debug('Congress %s table source service data is empty. '
                          'Unable to check data.', table_name)
                return False
            LOG.debug('Congress %s table source service data: %s',
                      table_name, service_data)
            table_data = (
                self.os_admin.congress_client.list_datasource_rows(
                    self.datasource_id, table_name)['results'])
            LOG.debug('Congress %s table data: %s', table_name, table_data)

            # check same cardinality
            if len(service_data) != len(table_data):
                LOG.debug('Cardinality mismatch between congress %s '
                          'table and service data', table_name)
                return False

            # construct map from id to service data items
            service_data_map = {}
            for data_item in service_data:
                service_data_map[data_item['id']] = data_item

            for row in table_data:
                try:
                    service_item = service_data_map[row['data'][table_id_col]]
                except KeyError:
                    return False
                for index in range(len(table_schema)):
                    # case: key is not present in service_item, allow
                    # if it is expected (sometimes an objects won't have key
                    # when the value is not present, e.g. description not set)
                    if (str(row['data'][index]) == 'None' and
                            table_schema[index][
                                'name'] in missing_attributes_allowed and
                            table_schema[index]['name'] not in service_item):
                        return True
                    # normal case: service_item value must equal
                    # congress table value
                    if (str(row['data'][index]) !=
                            str(service_item[table_schema[index]['name']])):
                        return False
            return True

        if not test_utils.call_until_true(
                func=_check_data, duration=100, sleep_for=4):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    def check_service_data_against_congress_subtable(
            self, table_name, service_data_fetch_func,
            service_subdata_attribute):
        def _check_data():
            # Fetch data each time, because test may go before service has data
            service_data = service_data_fetch_func()

            LOG.debug('Congress %s table source service data: %s',
                      table_name, service_data)
            table_data = (
                self.os_admin.congress_client.list_datasource_rows(
                    self.datasource_id, table_name)['results'])
            LOG.debug('Congress %s table data: %s', table_name, table_data)

            # construct map from id to service data items
            service_data_map = {}
            for data_item in service_data:
                service_data_map[data_item['id']] = data_item[
                    service_subdata_attribute]

            expected_number_of_rows = 0

            for row in table_data:
                row_id, row_data = row['data'][0], row['data'][1]
                service_subdata = service_data_map.get(row_id)
                if not service_subdata or row_data not in service_subdata:
                    # congress table has item not in service data.
                    LOG.debug('Congress %s table has row (%s, %s) not in '
                              'service data', table_name, row_id, row_data)
                    return False
                expected_number_of_rows += len(service_subdata)

            # check cardinality
            if expected_number_of_rows != len(table_data):
                LOG.debug('Cardinality mismatch between congress %s '
                          'table and service data', table_name)
                return False
            return True

        if not test_utils.call_until_true(
                func=_check_data,
                duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    @decorators.attr(type='smoke')
    def test_update_no_error(self):
        if not test_utils.call_until_true(
                func=lambda: self.check_datasource_no_error(
                    self.datasource_name),
                duration=30, sleep_for=5):
            raise exceptions.TimeoutException('Datasource could not poll '
                                              'without error.')
