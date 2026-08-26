"""Unit tests for SecurityProfilesOperatorHelm."""
#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# pylint: disable=protected-access

import unittest

from k8sapp_security_profiles_operator.common import (
    constants as app_constants,
)
from k8sapp_security_profiles_operator.helm import (
    security_profiles_operator as spo_helm,
)

SPOHelm = spo_helm.SecurityProfilesOperatorHelm


class TestSecurityProfilesOperatorHelm(unittest.TestCase):
    """Test SecurityProfilesOperatorHelm class."""

    def setUp(self):
        """Set up test instance."""
        self.helm = SPOHelm()

    def test_chart_attribute(self):
        """Verify CHART matches the expected constant."""
        expected = (
            app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR
        )
        self.assertEqual(self.helm.CHART, expected)

    def test_service_name(self):
        """Verify SERVICE_NAME is set correctly."""
        expected = (
            app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR
        )
        self.assertEqual(
            self.helm.SERVICE_NAME, expected
        )

    def test_supported_namespaces_contains_spo(self):
        """Verify SPO namespace in SUPPORTED_NAMESPACES."""
        spo_namespace = (
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR
        )
        self.assertIn(
            spo_namespace,
            self.helm.SUPPORTED_NAMESPACES
        )

    def test_supported_app_namespaces_key(self):
        """Verify SUPPORTED_APP_NAMESPACES has app key."""
        app_key = (
            app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR
        )
        self.assertIn(
            app_key,
            self.helm.SUPPORTED_APP_NAMESPACES
        )

    def test_supported_app_namespaces_contains_spo_ns(self):
        """Verify app namespaces include SPO namespace."""
        app_key = (
            app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR
        )
        spo_namespace = (
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR
        )
        app_namespaces = (
            self.helm.SUPPORTED_APP_NAMESPACES[app_key]
        )
        self.assertIn(spo_namespace, app_namespaces)

    def test_get_namespaces(self):
        """Verify get_namespaces returns expected list."""
        result = self.helm.get_namespaces()
        self.assertEqual(
            result, self.helm.SUPPORTED_NAMESPACES
        )

    def test_get_overrides_valid_namespace(self):
        """Verify overrides returned for valid namespace."""
        spo_namespace = (
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR
        )
        result = self.helm.get_overrides(
            namespace=spo_namespace
        )
        self.assertIsInstance(result, dict)

    def test_get_overrides_valid_namespace_empty(self):
        """Verify overrides for SPO namespace is empty."""
        spo_namespace = (
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR
        )
        result = self.helm.get_overrides(
            namespace=spo_namespace
        )
        self.assertEqual(result, {})

    def test_get_overrides_no_namespace(self):
        """Verify no namespace returns all overrides."""
        result = self.helm.get_overrides(namespace=None)
        self.assertIsInstance(result, dict)
        spo_namespace = (
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR
        )
        self.assertIn(spo_namespace, result)

    def test_get_overrides_invalid_namespace(self):
        """Verify raises for invalid namespace."""
        from sysinv.common import exception  # pylint: disable=import-outside-toplevel
        # pylint: disable=import-outside-toplevel
        with self.assertRaises(
            exception.InvalidHelmNamespace
        ):
            self.helm.get_overrides(
                namespace='invalid-ns'
            )


class TestSPOHelmClassAttributes(unittest.TestCase):
    """Test class-level attributes of SPOHelm."""

    def test_class_has_chart(self):
        """Verify class defines CHART."""
        self.assertTrue(hasattr(SPOHelm, 'CHART'))

    def test_class_has_service_name(self):
        """Verify class defines SERVICE_NAME."""
        self.assertTrue(
            hasattr(SPOHelm, 'SERVICE_NAME')
        )

    def test_class_has_supported_namespaces(self):
        """Verify class defines SUPPORTED_NAMESPACES."""
        self.assertTrue(
            hasattr(SPOHelm, 'SUPPORTED_NAMESPACES')
        )

    def test_class_has_supported_app_namespaces(self):
        """Verify class defines SUPPORTED_APP_NAMESPACES."""
        self.assertTrue(
            hasattr(
                SPOHelm, 'SUPPORTED_APP_NAMESPACES'
            )
        )


if __name__ == '__main__':
    unittest.main()
