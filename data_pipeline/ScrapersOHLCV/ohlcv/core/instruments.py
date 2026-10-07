"""Static index metadata; importing this module never contacts a provider."""
INDEXES = {
    'VNINDEX': {'name':'VN-Index', 'exchange':'HOSE'},
    'VN30': {'name':'VN30', 'exchange':'HOSE'},
    'HNXINDEX': {'name':'HNX-Index', 'exchange':'HNX'},
    'UPCOMINDEX': {'name':'UPCoM-Index', 'exchange':'UPCOM'},
}
INDEX_ALIASES = {'HNX':'HNXINDEX', 'UPCOM':'UPCOMINDEX'}
