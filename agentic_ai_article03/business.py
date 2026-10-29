ORDERS = {'ORD-1042': {'status':'shipped','tracking_id':'TRK-88'}}
TRACKING = {'TRK-88': {'status':'delayed at regional facility','last_update':'2026-10-27'}}
ALLOWED_ORDERS = {'ORD-1042'}

def order_lookup(order_id: str) -> dict:
    if order_id not in ALLOWED_ORDERS:
        return {'error':'not_authorized'}
    item = ORDERS.get(order_id)
    if item is None:
        return {'error':'not_found'}
    return {'order_id':order_id, **item}

def tracking_lookup(tracking_id: str) -> dict:
    authorized = {ORDERS[oid]['tracking_id'] for oid in ALLOWED_ORDERS if oid in ORDERS}
    if tracking_id not in authorized:
        return {'error':'not_authorized'}
    item = TRACKING.get(tracking_id)
    if item is None:
        return {'error':'not_found'}
    return {'tracking_id':tracking_id, **item}
