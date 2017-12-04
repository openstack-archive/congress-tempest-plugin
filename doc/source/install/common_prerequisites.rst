Prerequisites
-------------

Before you install and configure the congress service,
you must create a database, service credentials, and API endpoints.

#. To create the database, complete these steps:

   * Use the database access client to connect to the database
     server as the ``root`` user:

     .. code-block:: console

        $ mysql -u root -p

   * Create the ``congress_tempest_plugin`` database:

     .. code-block:: none

        CREATE DATABASE congress_tempest_plugin;

   * Grant proper access to the ``congress_tempest_plugin`` database:

     .. code-block:: none

        GRANT ALL PRIVILEGES ON congress_tempest_plugin.* TO 'congress_tempest_plugin'@'localhost' \
          IDENTIFIED BY 'CONGRESS_TEMPEST_PLUGIN_DBPASS';
        GRANT ALL PRIVILEGES ON congress_tempest_plugin.* TO 'congress_tempest_plugin'@'%' \
          IDENTIFIED BY 'CONGRESS_TEMPEST_PLUGIN_DBPASS';

     Replace ``CONGRESS_TEMPEST_PLUGIN_DBPASS`` with a suitable password.

   * Exit the database access client.

     .. code-block:: none

        exit;

#. Source the ``admin`` credentials to gain access to
   admin-only CLI commands:

   .. code-block:: console

      $ . admin-openrc

#. To create the service credentials, complete these steps:

   * Create the ``congress_tempest_plugin`` user:

     .. code-block:: console

        $ openstack user create --domain default --password-prompt congress_tempest_plugin

   * Add the ``admin`` role to the ``congress_tempest_plugin`` user:

     .. code-block:: console

        $ openstack role add --project service --user congress_tempest_plugin admin

   * Create the congress_tempest_plugin service entities:

     .. code-block:: console

        $ openstack service create --name congress_tempest_plugin --description "congress" congress

#. Create the congress service API endpoints:

   .. code-block:: console

      $ openstack endpoint create --region RegionOne \
        congress public http://controller:XXXX/vY/%\(tenant_id\)s
      $ openstack endpoint create --region RegionOne \
        congress internal http://controller:XXXX/vY/%\(tenant_id\)s
      $ openstack endpoint create --region RegionOne \
        congress admin http://controller:XXXX/vY/%\(tenant_id\)s
