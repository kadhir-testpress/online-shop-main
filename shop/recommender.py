import redis
from django.conf import settings
from .models import Product

redis_database = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )

class Recommender(object):
    def record_products_purchased(self, products):
        product_ids = [p.id for p in products]
        self._update_purchased_together_scores(product_ids)
    
    def get_product_recommendations(self, products, max_results=1):
        product_ids = [p.id for p in products]

        if len(products) == 1:
            suggestions = self._get_single_product_suggestions(product_ids[0], max_results)
        else:
            suggestions = self._get_multiple_product_suggestions(product_ids, max_results)

        suggested_products_ids = self._get_suggested_product_ids(suggestions)
        suggested_products = self._get_suggested_products(suggested_products_ids)

        return suggested_products
    
    def clear_purchase_history(self):
        for product_id in Product.objects.values_list('id', flat=True):
            redis_database.delete(self._get_product_key(product_id))
            
    def _update_purchased_together_scores(self, product_ids):
        for product_id in product_ids:
            for with_id in product_ids:
                if product_id != with_id:
                    redis_database.zincrby(
                        self._get_product_key(product_id),
                        1,
                        with_id
                    )
    
    def _get_single_product_suggestions(self, product_id, max_results):
        return redis_database.zrange(
            self._get_product_key(product_id),
            0, -1,
            desc=True
        )[:max_results]

    def _get_multiple_product_suggestions(self, product_ids, max_results):
        flat_ids = ''.join([str(id) for id in product_ids])
        tmp_key = f'tmp_{flat_ids}'

        keys = [self._get_product_key(id) for id in product_ids]
        redis_database.zunionstore(tmp_key, keys)

        redis_database.zrem(tmp_key, *product_ids)

        suggestions = redis_database.zrange(tmp_key, 0, -1, desc=True)[:max_results]

        redis_database.delete(tmp_key)
        return suggestions
    
    def _get_suggested_product_ids(self, suggestions):
        return [int(id) for id in suggestions]
    
    def _get_suggested_products(self, suggested_products_ids):
        suggested_products = list(Product.objects.filter(id__in=suggested_products_ids))
        suggested_products.sort(key=lambda x: suggested_products_ids.index(x.id))
        return suggested_products

    def _get_product_key(self, product_id):
        return f'product:{product_id}:purchased_with'
    

    
