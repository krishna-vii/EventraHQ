"""Read-only connection diagnosis; never print provider exceptions or credentials."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'api'))
from app.settings import Settings
from app.persistence import Database

try:
    with Database(Settings.from_environment()).connect() as connection:
        connection.execute('select 1')
    print('Database connection: ready')
except Exception as error:
    message = str(error).lower()
    categories = {
        'password authentication failed': 'Stored runtime password was rejected.',
        'certificate verify failed': 'Database certificate verification failed.',
        'timeout': 'Database connection timed out.',
        'could not translate host name': 'Database hostname could not be resolved.',
        'tenant or user not found': 'Pooler could not locate the configured project or role.',
        'connection refused': 'Database endpoint refused the connection.',
        'circuit breaker': 'Pooler authentication circuit breaker is open.',
        'server closed': 'Database server closed the connection.',
        'received invalid response': 'Unexpected response from the database endpoint.',
        'ssl': 'Database TLS negotiation failed.',
        'failed to resolve': 'Database hostname could not be resolved.',
        'getaddrinfo': 'Database hostname could not be resolved.',
        'no such host': 'Database hostname could not be resolved.',
        'connection is bad': 'Database transport could not establish a connection.',
        'max client connections': 'Database connection capacity is exhausted.',
    }
    print(next((safe for marker, safe in categories.items() if marker in message), 'Database connection failed; error category: ' + type(error).__name__))
    sys.exit(1)
