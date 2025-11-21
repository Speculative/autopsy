"""Example: KV Store with transactions demonstrating autopsy report logging."""

import random
from typing import Any, Dict, List, Optional, Tuple

from autopsy import call_stack, report


class KVStore:
    """Simple in-memory key-value store."""

    def __init__(self):
        """Initialize an empty store."""
        self._data: Dict[str, Any] = {}
        self._access_count = 0
        self._write_count = 0

    def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        self._access_count += 1
        value = self._data.get(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a key-value pair."""
        self._write_count += 1
        self._data[key] = value

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if key existed."""
        if key in self._data:
            self._write_count += 1
            del self._data[key]
            return True
        return False

    def size(self) -> int:
        """Get the number of keys in the store."""
        return len(self._data)

    def keys(self) -> List[str]:
        """Get all keys in the store."""
        return list(self._data.keys())

    def get_stats(self) -> Dict[str, int]:
        """Get access statistics."""
        return {
            "access_count": self._access_count,
            "write_count": self._write_count,
            "size": self.size(),
        }


class Transaction:
    """Represents a transaction with a list of operations."""

    def __init__(self, tx_id: str):
        """Initialize a transaction."""
        self.tx_id = tx_id
        self.operations: List[Tuple[str, str, Any]] = []  # (op_type, key, value)
        self.committed = False
        self.rolled_back = False

    def add_operation(self, op_type: str, key: str, value: Any = None) -> None:
        """Add an operation to the transaction."""
        if self.committed or self.rolled_back:
            raise ValueError("Cannot modify committed or rolled back transaction")
        self.operations.append((op_type, key, value))

    def commit(self, store: KVStore) -> None:
        """Apply all operations to the store."""
        if self.committed:
            raise ValueError("Transaction already committed")
        if self.rolled_back:
            raise ValueError("Cannot commit rolled back transaction")

        for op_type, key, value in self.operations:
            if op_type == "set":
                store.set(key, value)
            elif op_type == "delete":
                store.delete(key)

        self.committed = True

    def rollback(self) -> None:
        """Mark transaction as rolled back."""
        if self.committed:
            raise ValueError("Cannot rollback committed transaction")
        self.rolled_back = True


class TransactionManager:
    """Manages transactions for a KV store."""

    def __init__(self, store: KVStore):
        """Initialize transaction manager with a store."""
        self.store = store
        self.active_transactions: Dict[str, Transaction] = {}
        self.committed_transactions: List[str] = []
        self.rolled_back_transactions: List[str] = []

    def begin_transaction(self, tx_id: Optional[str] = None) -> Transaction:
        """Begin a new transaction."""
        if tx_id is None:
            tx_id = f"tx_{len(self.active_transactions) + len(self.committed_transactions) + len(self.rolled_back_transactions)}"
        tx = Transaction(tx_id)
        self.active_transactions[tx_id] = tx
        report.log(tx_id, len(self.active_transactions))
        return tx

    def commit_transaction(self, tx_id: str) -> bool:
        """Commit a transaction. Returns True if successful."""
        if tx_id not in self.active_transactions:
            report.log("commit_failed", tx_id, "not_active")
            return False
        tx = self.active_transactions[tx_id]
        num_ops = len(tx.operations)
        tx.commit(self.store)
        del self.active_transactions[tx_id]
        self.committed_transactions.append(tx_id)
        report.log(tx_id, num_ops, len(self.committed_transactions))
        return True

    def rollback_transaction(self, tx_id: str) -> bool:
        """Rollback a transaction. Returns True if successful."""
        if tx_id not in self.active_transactions:
            report.log("rollback_failed", tx_id, "not_active")
            return False
        tx = self.active_transactions[tx_id]
        num_ops = len(tx.operations)
        tx.rollback()
        del self.active_transactions[tx_id]
        self.rolled_back_transactions.append(tx_id)
        report.log(tx_id, num_ops, len(self.rolled_back_transactions))
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get transaction statistics."""
        return {
            "active": len(self.active_transactions),
            "committed": len(self.committed_transactions),
            "rolled_back": len(self.rolled_back_transactions),
            "store_stats": self.store.get_stats(),
        }


def generate_random_transaction(
    manager: TransactionManager, max_ops: int = 5
) -> Transaction:
    """Generate a random transaction with random operations."""
    tx = manager.begin_transaction()
    num_ops = random.randint(1, max_ops)

    keys = [
        "user:1",
        "user:2",
        "user:3",
        "product:1",
        "product:2",
        "order:1",
        "order:2",
    ]
    operations = ["set", "delete"]

    for _ in range(num_ops):
        op_type = random.choice(operations)
        key = random.choice(keys)
        if op_type == "set":
            value = random.choice(
                ["active", "pending", "completed", random.randint(1, 100)]
            )
            tx.add_operation(op_type, key, value)
            report.log("tx_operation", tx.tx_id, op_type, key, value)
        else:
            tx.add_operation(op_type, key)
            report.log("tx_operation", tx.tx_id, op_type, key)

    report.log("tx_created", tx.tx_id, len(tx.operations), manager.get_stats())
    return tx


def simulate_transaction_workload(
    manager: TransactionManager, num_transactions: int = 10
) -> None:
    """Simulate a workload of random transactions."""
    transactions: List[Transaction] = []

    for i in range(num_transactions):
        tx = generate_random_transaction(manager)
        transactions.append(tx)

        report.log("workload_progress", i + 1, num_transactions, manager.get_stats())

        commit_probability = 0.7
        if random.random() < commit_probability:
            manager.commit_transaction(tx.tx_id)
            report.log("tx_committed", tx.tx_id, manager.store.get_stats())
        else:
            manager.rollback_transaction(tx.tx_id)
            report.log("tx_rolled_back", tx.tx_id, len(tx.operations))

    report.log("workload_complete", len(transactions), manager.get_stats())


def analyze_store_state(store: KVStore) -> None:
    """Analyze and log the current state of the store."""
    stats = store.get_stats()
    keys = store.keys()

    report.log("store_analysis", stats, keys)

    for key in keys[:5]:
        value = store.get(key)
        report.log("store_entry", key, value)


def run_example() -> None:
    """Run the KV store example and populate the report."""
    print("Initializing KV store and transaction manager...")
    store = KVStore()
    manager = TransactionManager(store)

    # Use call_stack() to capture stack trace for this log entry
    cs = call_stack()
    report.log(cs, "system_init", store.get_stats(), manager.get_stats())

    print("Running transaction workload...")
    simulate_transaction_workload(manager, num_transactions=15)

    print("Analyzing final store state...")
    analyze_store_state(store)

    print(f"✓ Store contains {store.size()} keys")
    print(f"✓ Final stats: {store.get_stats()}")
