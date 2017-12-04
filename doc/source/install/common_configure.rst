2. Edit the ``/etc/congress_tempest_plugin/congress_tempest_plugin.conf`` file and complete the following
   actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: ini

        [database]
        ...
        connection = mysql+pymysql://congress_tempest_plugin:CONGRESS_TEMPEST_PLUGIN_DBPASS@controller/congress_tempest_plugin
