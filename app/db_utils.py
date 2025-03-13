from firebase_admin import firestore
from concurrent.futures import ThreadPoolExecutor
import time

db = firestore.client()

def batch_get(doc_refs):
    """Efficiently get multiple documents by reference"""
    # Use Firestore's built-in batched get
    docs = db.get_all(doc_refs)
    result = {}
    
    for doc in docs:
        if doc.exists:
            result[doc.id] = doc.to_dict()
        else:
            result[doc.id] = None
            
    return result

def batch_write(operations, max_batch_size=500):
    """
    Execute multiple write operations in batches
    
    Args:
        operations: List of (operation_type, ref, data) tuples
            where operation_type is 'set', 'update', or 'delete'
        max_batch_size: Maximum batch size (Firestore limit is 500)
    """
    if not operations:
        return []
        
    result = []
    batches = []
    current_batch = db.batch()
    current_batch_size = 0
    
    for op_type, ref, data in operations:
        # If batch is full, commit and create new batch
        if current_batch_size >= max_batch_size:
            batches.append(current_batch)
            current_batch = db.batch()
            current_batch_size = 0
            
        # Add operation to current batch
        if op_type == 'set':
            current_batch.set(ref, data)
        elif op_type == 'update':
            current_batch.update(ref, data)
        elif op_type == 'delete':
            current_batch.delete(ref)
        else:
            raise ValueError(f"Unknown operation type: {op_type}")
            
        current_batch_size += 1
        
    # Add the last batch if it has operations
    if current_batch_size > 0:
        batches.append(current_batch)
        
    # Commit all batches
    start_time = time.time()
    
    for batch in batches:
        batch.commit()
        result.append(True)
    
    execution_time = time.time() - start_time
    print(f"Batch operation completed in {execution_time:.2f}s")
    
    return result

def parallel_operations(operations, max_workers=5):
    """
    Execute multiple independent Firestore operations in parallel
    
    Args:
        operations: List of (function, args, kwargs) tuples to execute
        max_workers: Maximum number of parallel workers
    """
    results = []
    
    def execute_operation(operation):
        func, args, kwargs = operation
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(execute_operation, operations))
        
    return results