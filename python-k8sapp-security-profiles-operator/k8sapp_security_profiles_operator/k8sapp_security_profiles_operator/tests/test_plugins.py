#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from k8sapp_security_profiles_operator.common import constants as app_constants
from sysinv.tests.helm.test_helm import HelmOperatorTestSuiteMixin

from sysinv.tests.db import base as dbbase


class K8SAppSecurityProfilesOperatorAppMixin(object):
    app_name = app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR
    path_name = app_name + '.tgz'

    def setUp(self):
        super(K8SAppSecurityProfilesOperatorAppMixin, self).setUp()


# Test Configuration:
# - Controller
# - IPv6
# - Ceph Storage
# - security-profiles-operator app
class K8SAppSecurityProfilesOperatorControllerTestCase(K8SAppSecurityProfilesOperatorAppMixin,
                                         dbbase.BaseIPv6Mixin,
                                         dbbase.BaseCephStorageBackendMixin,
                                         HelmOperatorTestSuiteMixin,
                                         dbbase.ControllerHostTestCase):
    pass


# Test Configuration:
# - AIO
# - IPv4
# - Ceph Storage
# - security-profiles-operator app
class K8SAppSecurityProfilesOperatorAIOTestCase(K8SAppSecurityProfilesOperatorAppMixin,
                                  dbbase.BaseCephStorageBackendMixin,
                                  HelmOperatorTestSuiteMixin,
                                  dbbase.AIOSimplexHostTestCase):
    pass
