from app import create_app
from blockchain import Blockchain
app = create_app()
with app.app_context():
    print(Blockchain.validate_chain())
