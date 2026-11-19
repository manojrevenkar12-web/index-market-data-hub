"""Vendor adapters register themselves on import; `VendorAdapter.for_vendor(name)` dispatches on the vendor."""
from imdh.vendors import kestrel, meridian, northwind  # noqa: F401
from imdh.vendors.base import VendorAdapter, VendorFormatError

__all__ = ["VendorAdapter", "VendorFormatError"]
