"""Pre-built Enterprise OpenAPI 3.0 templates ready for Salesforce External Services registration."""

from __future__ import annotations

import json
from typing import Any, Dict


PAYMENT_SERVICE_SPEC: Dict[str, Any] = {
    "openapi": "3.0.1",
    "info": {
        "title": "AgentChaos Payment & Refund Service",
        "description": "Mock payment processing service for Salesforce Agentforce External Services testing",
        "version": "1.0.0",
    },
    "servers": [{"url": "http://localhost:8080"}],
    "paths": {
        "/payments/refund": {
            "post": {
                "summary": "Process Customer Refund",
                "description": "Submits a refund request to downstream core payment processor",
                "operationId": "processRefund",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["orderId", "amount"],
                                "properties": {
                                    "orderId": {"type": "string", "example": "ORD-9901"},
                                    "amount": {"type": "number", "example": 49.99},
                                    "reason": {"type": "string", "example": "Item damaged on arrival"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Refund processed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["refundId", "status", "refundAmount"],
                                    "properties": {
                                        "refundId": {"type": "string", "example": "REF-88492"},
                                        "status": {"type": "string", "example": "COMPLETED"},
                                        "refundAmount": {"type": "number", "example": 49.99},
                                        "timestamp": {"type": "string", "example": "2026-09-27T12:00:00Z"},
                                    },
                                }
                            }
                        },
                    },
                    "400": {"description": "Invalid refund parameters or expired return window"},
                    "500": {"description": "Internal payment ledger error"},
                    "504": {"description": "Downstream banking gateway timeout"},
                },
            }
        }
    },
}

ORDER_SERVICE_SPEC: Dict[str, Any] = {
    "openapi": "3.0.1",
    "info": {
        "title": "AgentChaos Order & Shipping Service",
        "description": "Order inquiry and tracking service for Salesforce Agentforce External Services testing",
        "version": "1.0.0",
    },
    "servers": [{"url": "http://localhost:8080"}],
    "paths": {
        "/orders/status": {
            "get": {
                "summary": "Get Order Tracking Status",
                "description": "Retrieves real-time fulfillment status and tracking number for an order",
                "operationId": "getOrderStatus",
                "parameters": [
                    {
                        "name": "orderId",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "ORD-5542",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Order details retrieved",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["orderId", "status"],
                                    "properties": {
                                        "orderId": {"type": "string", "example": "ORD-5542"},
                                        "status": {"type": "string", "example": "SHIPPED"},
                                        "carrier": {"type": "string", "example": "FedEx"},
                                        "trackingNumber": {"type": "string", "example": "TRK-9928172"},
                                        "estimatedDelivery": {"type": "string", "example": "2026-10-02"},
                                    },
                                }
                            }
                        },
                    },
                    "404": {"description": "Order not found"},
                    "504": {"description": "Fulfillment warehouse API timeout"},
                },
            }
        }
    },
}

CUSTOMER_SERVICE_SPEC: Dict[str, Any] = {
    "openapi": "3.0.1",
    "info": {
        "title": "AgentChaos Customer & VIP Service",
        "description": "Customer verification and entitlement service for Agentforce",
        "version": "1.0.0",
    },
    "servers": [{"url": "http://localhost:8080"}],
    "paths": {
        "/customers/verify": {
            "post": {
                "summary": "Verify Customer VIP Entitlement",
                "operationId": "verifyCustomerVIP",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["customerId"],
                                "properties": {
                                    "customerId": {"type": "string", "example": "CUST-1002"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Entitlement details retrieved",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["customerId", "tier"],
                                    "properties": {
                                        "customerId": {"type": "string", "example": "CUST-1002"},
                                        "tier": {"type": "string", "example": "PLATINUM_VIP"},
                                        "maxDiscretionaryCredit": {"type": "number", "example": 250.0},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        }
    },
}

PREBUILT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "payment": PAYMENT_SERVICE_SPEC,
    "order": ORDER_SERVICE_SPEC,
    "customer": CUSTOMER_SERVICE_SPEC,
}


def get_template_spec(template_name: str, base_url: str = "http://localhost:8080") -> Dict[str, Any]:
    """Retrieve an OpenAPI 3.0 specification updated with the desired server base URL."""
    spec = PREBUILT_TEMPLATES.get(template_name.lower())
    if not spec:
        raise ValueError(f"Unknown template '{template_name}'. Available: {list(PREBUILT_TEMPLATES.keys())}")
    
    # Return a deepcopy with updated server URL
    copied = json.loads(json.dumps(spec))
    copied["servers"] = [{"url": base_url}]
    return copied
