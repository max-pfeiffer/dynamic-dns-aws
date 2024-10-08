"""Tests for lambda_handler function."""

from secrets import token_hex
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from aws.lambda_function import lambda_handler


def test_lambda_handler(
    mocked_route_53_client: MagicMock, mocked_secrets_manager_cache: MagicMock
) -> None:
    """Test the happy path for lambda_handler().

    :type mocked_route_53_client: MagicMock
    :param mocked_route_53_client:
    :type mocked_secrets_manager_cache: MagicMock
    :param mocked_secrets_manager_cache:
    :return:
    """
    client_id = str(uuid4())
    test_token = token_hex()
    event: dict = {
        "queryStringParameters": {
            "client_id": client_id,
            "domain": "test_domain",
            "ip": "127.0.0.1",
            "token": test_token,
        }
    }
    mocked_secrets_manager_cache.get_secret_string.return_value = test_token

    response: dict = lambda_handler(event, {})

    assert response["statusCode"] == 200
    mocked_route_53_client.list_resource_record_sets.assert_called_once()
    mocked_route_53_client.change_resource_record_sets.assert_called_once()


def test_lambda_handler_invalid_token(
    mocked_route_53_client: MagicMock, mocked_secrets_manager_cache: MagicMock
) -> None:
    """Test calling lambda_handler() with an invalid token.

    :type mocked_route_53_client: MagicMock
    :param mocked_route_53_client:
    :type mocked_secrets_manager_cache: MagicMock
    :param mocked_secrets_manager_cache:
    :return:
    """
    client_id = str(uuid4())
    test_token = token_hex()
    event: dict = {
        "queryStringParameters": {
            "client_id": client_id,
            "domain": "test_domain",
            "ip": "127.0.0.1",
            "token": "invalid_token",
        }
    }
    mocked_secrets_manager_cache.get_secret_string.return_value = test_token

    response: dict = lambda_handler(event, {})

    assert response["statusCode"] == 401
    mocked_route_53_client.list_resource_record_sets.assert_not_called()
    mocked_route_53_client.change_resource_record_sets.assert_not_called()


@pytest.mark.parametrize(
    "event",
    [
        {
            "queryStringParameters": {
                "client_id": str(uuid4()),
                "domain": "test_domain",
                "ip": "127.0.0.1",
            }
        },
        {
            "queryStringParameters": {
                "client_id": str(uuid4()),
                "domain": "test_domain",
            }
        },
        {
            "queryStringParameters": {
                "client_id": str(uuid4()),
            }
        },
        {"queryStringParameters": {}},
    ],
)
def test_lambda_handler_missing_query_parameters(
    event: dict,
    mocked_route_53_client: MagicMock,
    mocked_secrets_manager_cache: MagicMock,
) -> None:
    """Test lambda_handler() with a missing query parameters.

    :type event: dict
    :param event:
    :type mocked_route_53_client: MagicMock
    :param mocked_route_53_client:
    :type mocked_secrets_manager_cache: MagicMock
    :param mocked_secrets_manager_cache:
    :return:
    """
    response: dict = lambda_handler(event, {})

    assert response["statusCode"] == 400
    mocked_secrets_manager_cache.get_secret_string.assert_not_called()
    mocked_route_53_client.list_resource_record_sets.assert_not_called()
    mocked_route_53_client.change_resource_record_sets.assert_not_called()


@pytest.mark.parametrize(
    "domain, ip, dns_record_needs_update",
    [
        (
            "foo.bar",
            "123.134.84.62",
            False,
        ),
        (
            "boom.bang",
            "231.134.85.63",
            False,
        ),
        ("cling.clang", "156.167.66.66", True),
        ("foo.bar", "192.168.23.162", True),
        ("boom.bang", "231.134.85.64", True),
    ],
)
def test_lambda_handler_multiple_dns_entries(
    mocked_route_53_client: MagicMock,
    mocked_secrets_manager_cache: MagicMock,
    route_53_client_response: dict,
    domain: str,
    ip: str,
    dns_record_needs_update: bool,
) -> None:
    """Test if lambda_handler() deals correctly with multiple DNS records.

    :type mocked_route_53_client: MagicMock
    :param mocked_route_53_client:
    :type mocked_secrets_manager_cache: MagicMock
    :param mocked_secrets_manager_cache:
    :param route_53_client_response:
    :type domain: str
    :param domain:
    :type ip: str
    :param ip:
    :type dns_record_needs_update: bool
    :param dns_record_needs_update:
    :return:
    """
    client_id = str(uuid4())
    test_token = token_hex()
    event: dict = {
        "queryStringParameters": {
            "client_id": client_id,
            "domain": domain,
            "ip": ip,
            "token": test_token,
        }
    }
    mocked_secrets_manager_cache.get_secret_string.return_value = test_token
    mocked_route_53_client.list_resource_record_sets.return_value = (
        route_53_client_response
    )

    response: dict = lambda_handler(event, {})

    assert response["statusCode"] == 200
    assert "DNS record was updated" in response["body"]
    mocked_route_53_client.list_resource_record_sets.assert_called_once()
    if dns_record_needs_update:
        mocked_route_53_client.change_resource_record_sets.assert_called_once()
        changes = mocked_route_53_client.change_resource_record_sets.call_args.kwargs[
            "ChangeBatch"
        ]["Changes"]
        assert changes
        assert changes[0]["ResourceRecordSet"]["Name"] == domain
        assert changes[0]["ResourceRecordSet"]["ResourceRecords"][0]["Value"] == ip


def test_lambda_handler_multiple_domains(
    mocked_route_53_client: MagicMock,
    mocked_secrets_manager_cache: MagicMock,
    route_53_client_response: dict,
) -> None:
    """Test lambda_handler() with multiple domains in query parameter.

    :type mocked_route_53_client: MagicMock
    :param mocked_route_53_client:
    :type mocked_secrets_manager_cache: MagicMock
    :param mocked_secrets_manager_cache:
    :type route_53_client_response: dict
    :param route_53_client_response:
    :return:
    """
    domains = "foo.bar,boom.bang"
    ip = "123.45.67.89"
    client_id = str(uuid4())
    test_token = token_hex()
    event: dict = {
        "queryStringParameters": {
            "client_id": client_id,
            "domain": domains,
            "ip": ip,
            "token": test_token,
        }
    }
    mocked_secrets_manager_cache.get_secret_string.return_value = test_token
    mocked_route_53_client.list_resource_record_sets.return_value = (
        route_53_client_response
    )

    response: dict = lambda_handler(event, {})
    assert response["statusCode"] == 200
    assert "DNS record was updated" in response["body"]
    mocked_route_53_client.list_resource_record_sets.assert_called_once()
    mocked_route_53_client.change_resource_record_sets.assert_called_once()
    changes = mocked_route_53_client.change_resource_record_sets.call_args.kwargs[
        "ChangeBatch"
    ]["Changes"]
    assert len(changes) == 2
    for index, domain in enumerate(sorted(domains.split(","))):
        assert changes[index]["ResourceRecordSet"]["Name"] == domain
        assert changes[index]["ResourceRecordSet"]["ResourceRecords"][0]["Value"] == ip
