#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Unit tests for constants module."""

import unittest

from k8sapp_security_profiles_operator.common import (
    constants as app_constants,
)


class TestConstants(unittest.TestCase):
    """Test constants module values."""

    def test_helm_app_name(self):
        """Verify HELM_APP name value."""
        self.assertEqual(
            app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
            'security-profiles-operator'
        )

    def test_helm_namespace(self):
        """Verify HELM_NS namespace value."""
        self.assertEqual(
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            'security-profiles-operator'
        )

    def test_helm_chart_name(self):
        """Verify HELM_CHART name value."""
        self.assertEqual(
            app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR,
            'security-profiles-operator'
        )

    def test_helm_component_label(self):
        """Verify HELM_COMPONENT_LABEL_SPO value."""
        self.assertEqual(
            app_constants.HELM_COMPONENT_LABEL_SPO,
            'app.starlingx.io/component'
        )

    def test_constants_are_strings(self):
        """Verify all HELM_ constants are string type."""
        constants = [
            (name, getattr(app_constants, name))
            for name in dir(app_constants)
            if name.startswith('HELM_')
            and not callable(getattr(app_constants, name))
        ]
        for name, value in constants:
            self.assertIsInstance(
                value, str, f"{name} is not a string"
            )

    def test_constants_not_empty(self):
        """Verify all HELM_ constants are not empty strings."""
        constants = [
            (name, getattr(app_constants, name))
            for name in dir(app_constants)
            if name.startswith('HELM_')
            and not callable(getattr(app_constants, name))
        ]
        for name, value in constants:
            self.assertTrue(
                value, f"{name} is empty"
            )

    def test_namespace_matches_app_name(self):
        """Verify namespace equals app name."""
        self.assertEqual(
            app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR
        )

    def test_chart_matches_app_name(self):
        """Verify chart name equals app name."""
        self.assertEqual(
            app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
            app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR
        )


if __name__ == '__main__':
    unittest.main()
