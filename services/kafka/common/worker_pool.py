"""
Worker Pool Management
Manages thread pools for Kafka consumers
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Callable, Any, Optional
import structlog

logger = structlog.get_logger()


class WorkerPool:
    """Manages thread pools for Kafka consumer workers"""
    
    def __init__(self):
        self.pools: Dict[str, ThreadPoolExecutor] = {}
        self.active_tasks: Dict[str, List[Future]] = {}
        self.pool_stats: Dict[str, Dict] = {}
        self.running = False
        
    def create_pool(self, pool_name: str, max_workers: int = 10) -> ThreadPoolExecutor:
        """Create a new thread pool"""
        if pool_name in self.pools:
            logger.warning("create_worker_pool_already_exists", action="create_pool", pool_name=pool_name)
            return self.pools[pool_name]
        
        pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"{pool_name}-worker"
        )
        
        self.pools[pool_name] = pool
        self.active_tasks[pool_name] = []
        self.pool_stats[pool_name] = {
            "created_at": time.time(),
            "max_workers": max_workers,
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0
        }
        
        logger.info(
            "create_worker_pool_success",
            action="create_pool",
            pool_name=pool_name,
            max_workers=max_workers
        )
        
        return pool
    
    def submit_task(self, pool_name: str, func: Callable, *args, **kwargs) -> Future:
        """Submit a task to a specific pool"""
        if pool_name not in self.pools:
            raise ValueError(f"Pool not found: {pool_name}")
        
        pool = self.pools[pool_name]
        future = pool.submit(func, *args, **kwargs)
        
        self.active_tasks[pool_name].append(future)
        self.pool_stats[pool_name]["total_tasks"] += 1
        
        # Add callback to track completion
        future.add_done_callback(
            lambda f: self._task_completed(pool_name, f)
        )
        
        logger.debug(
            "submit_worker_task_success",
            action="submit_task",
            pool_name=pool_name,
            task_id=id(future)
        )
        
        return future
    
    def _task_completed(self, pool_name: str, future: Future):
        """Handle task completion"""
        try:
            result = future.result()
            self.pool_stats[pool_name]["completed_tasks"] += 1
            
            logger.debug(
                "worker_task_completed",
                action="_task_completed",
                pool_name=pool_name,
                task_id=id(future)
            )

        except Exception as e:
            self.pool_stats[pool_name]["failed_tasks"] += 1

            logger.error(
                "worker_task_failed",
                action="_task_completed",
                pool_name=pool_name,
                task_id=id(future),
                **{"error.code": "TASK", "error.message": str(e)},
                exc_info=True
            )
        
        finally:
            # Remove from active tasks
            if future in self.active_tasks[pool_name]:
                self.active_tasks[pool_name].remove(future)
    
    def get_pool(self, pool_name: str) -> Optional[ThreadPoolExecutor]:
        """Get a specific pool"""
        return self.pools.get(pool_name)
    
    def remove_pool(self, pool_name: str, wait_for_completion: bool = True):
        """Remove a pool"""
        if pool_name not in self.pools:
            logger.warning("remove_worker_pool_not_found", action="remove_pool", pool_name=pool_name)
            return
        
        pool = self.pools[pool_name]
        
        if wait_for_completion:
            logger.debug(
                "remove_worker_pool_waiting",
                action="remove_pool",
                pool_name=pool_name,
                active_tasks=len(self.active_tasks[pool_name])
            )
            
            # Wait for all active tasks to complete
            for future in self.active_tasks[pool_name]:
                try:
                    future.result(timeout=30)  # Wait up to 30 seconds per task
                except Exception:
                    pass  # Already logged in _task_completed
        
        # Shutdown the pool
        pool.shutdown(wait=wait_for_completion)
        
        # Clean up
        del self.pools[pool_name]
        del self.active_tasks[pool_name]
        del self.pool_stats[pool_name]
        
        logger.info(
            "remove_worker_pool_success",
            action="remove_pool",
            pool_name=pool_name
        )
    
    def get_pool_stats(self, pool_name: str) -> Optional[Dict]:
        """Get statistics for a specific pool"""
        if pool_name not in self.pool_stats:
            return None
        
        stats = self.pool_stats[pool_name].copy()
        stats.update({
            "active_tasks": len(self.active_tasks[pool_name]),
            "pool_size": self.pools[pool_name]._max_workers,
            "uptime": time.time() - stats["created_at"]
        })
        
        return stats
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all pools"""
        return {
            pool_name: self.get_pool_stats(pool_name)
            for pool_name in self.pools.keys()
        }
    
    def cleanup_completed_tasks(self, pool_name: str = None):
        """Clean up completed tasks"""
        pools_to_clean = [pool_name] if pool_name else list(self.pools.keys())
        
        for p_name in pools_to_clean:
            if p_name not in self.active_tasks:
                continue
            
            # Filter out completed tasks
            before_count = len(self.active_tasks[p_name])
            self.active_tasks[p_name] = [
                future for future in self.active_tasks[p_name]
                if not future.done()
            ]
            after_count = len(self.active_tasks[p_name])
            
            if before_count != after_count:
                logger.debug(
                    "cleanup_completed_tasks_done",
                    action="cleanup_completed_tasks",
                    pool_name=p_name,
                    cleaned_count=before_count - after_count
                )
    
    def wait_for_completion(self, pool_name: str, timeout: float = None) -> bool:
        """Wait for all tasks in a pool to complete"""
        if pool_name not in self.pools:
            return False
        
        pool = self.pools[pool_name]
        
        # Wait for all futures
        futures = self.active_tasks[pool_name].copy()
        
        if not futures:
            return True
        
        try:
            for future in futures:
                future.result(timeout=timeout)
            return True
            
        except Exception as e:
            logger.error(
                "wait_worker_pool_completion_failed",
                action="wait_for_completion",
                pool_name=pool_name,
                **{"error.code": "TASK", "error.message": str(e)}
            )
            return False
    
    def cancel_tasks(self, pool_name: str, only_pending: bool = True) -> int:
        """Cancel tasks in a pool"""
        if pool_name not in self.active_tasks:
            return 0
        
        cancelled_count = 0
        
        for future in self.active_tasks[pool_name]:
            if only_pending and future.running():
                continue
                
            if future.cancel():
                cancelled_count += 1
        
        logger.info(
            "cancel_worker_tasks_success",
            action="cancel_tasks",
            pool_name=pool_name,
            cancelled_count=cancelled_count
        )
        
        # Clean up cancelled tasks
        self.cleanup_completed_tasks(pool_name)
        
        return cancelled_count
    
    def scale_pool(self, pool_name: str, new_max_workers: int):
        """Scale a pool to a new size"""
        if pool_name not in self.pools:
            raise ValueError(f"Pool not found: {pool_name}")
        
        old_pool = self.pools[pool_name]
        old_max_workers = old_pool._max_workers
        
        if old_max_workers == new_max_workers:
            return
        
        # Create new pool with desired size
        new_pool = ThreadPoolExecutor(
            max_workers=new_max_workers,
            thread_name_prefix=f"{pool_name}-worker"
        )
        
        # Wait for old pool to complete current tasks
        old_pool.shutdown(wait=True)
        
        # Replace pool
        self.pools[pool_name] = new_pool
        self.pool_stats[pool_name]["max_workers"] = new_max_workers
        
        logger.info(
            "scale_worker_pool_success",
            action="scale_pool",
            pool_name=pool_name,
            old_workers=old_max_workers,
            new_workers=new_max_workers
        )
    
    def shutdown_all(self, wait_for_completion: bool = True):
        """Shutdown all pools"""
        logger.info("shutdown_all_worker_pools_started", action="shutdown_all")

        pool_names = list(self.pools.keys())

        for pool_name in pool_names:
            self.remove_pool(pool_name, wait_for_completion)

        logger.info("shutdown_all_worker_pools_success", action="shutdown_all")
    
    def health_check(self) -> Dict:
        """Perform health check on all pools"""
        health = {
            "healthy": True,
            "total_pools": len(self.pools),
            "unhealthy_pools": [],
            "pool_details": {}
        }
        
        for pool_name in self.pools.keys():
            stats = self.get_pool_stats(pool_name)
            
            if not stats:
                health["unhealthy_pools"].append(pool_name)
                health["healthy"] = False
                continue
            
            # Check for too many failed tasks
            if stats["failed_tasks"] > stats["completed_tasks"] * 0.1:  # 10% failure rate
                health["unhealthy_pools"].append(pool_name)
                health["healthy"] = False
            
            health["pool_details"][pool_name] = stats
        
        return health
