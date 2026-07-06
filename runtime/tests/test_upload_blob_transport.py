"""Regression guard for the dev upload 503 (2026-07-06).

`upload.py::_persist` uploads via the ASYNC azure blob client
(``azure.storage.blob.aio.BlobServiceClient``), whose transport is powered by **aiohttp** —
which was missing from the dependencies, so the client ImportErrored at request time and the
broad ``except`` surfaced it as a 503. It also handed the SYNC ``DefaultAzureCredential`` to
the async client.

These tests exercise the real aio import + construction path so a missing transport dep (or a
sync/async credential mismatch) fails HERE in CI, not as a production 503.
"""

from __future__ import annotations


def test_aio_blob_transport_dependency_is_installed():
    # The exact dependency that was missing. aiohttp powers azure's async HTTP transport;
    # importing AioHttpTransport requires it, so this import is a precise guard.
    import aiohttp  # noqa: F401
    from azure.core.pipeline.transport import AioHttpTransport

    assert AioHttpTransport is not None


async def test_persist_aio_client_and_credential_construct():
    """Mirror upload.py::_persist's imports + construction EXACTLY: the async blob client
    paired with the ASYNC credential, both entered as async context managers (which is also
    what closes the aiohttp session cleanly). No network — construction alone instantiates
    the aio transport, which is where the missing-aiohttp failure occurred."""
    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import BlobServiceClient

    async with DefaultAzureCredential() as cred, BlobServiceClient(
        account_url="https://example.blob.core.windows.net", credential=cred
    ) as svc:
        # The container client is what _persist calls upload_blob on; getting it proves the
        # aio pipeline (transport included) built successfully.
        assert svc.get_container_client("uploads") is not None
