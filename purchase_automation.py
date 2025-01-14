from models import db, PurchasePlan, PurchaseOrder
import requests
import logging

logger = logging.getLogger(__name__)

def create_external_order(item_name, quantity, supplier):
    """
    Отправляет заказ внешнему поставщику через API.
    Возвращает ID заказа во внешней системе.
    """
    api_url = "https://api.supplier.com/orders"  # Заменить на реальный URL API
    payload = {
        "item_name": item_name,
        "quantity": quantity,
        "supplier": supplier
    }
    headers = {
        "Authorization": "Bearer YOUR_API_KEY",  # Заменить на реальный API-ключ
        "Content-Type": "application/json"
    }

    try:
        logger.info(f"Отправка запроса к API: {api_url}")
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()  
        order_data = response.json()
        logger.info(f"Ответ от API: {order_data}")
        return order_data.get("order_id")  # Предполагаем, что API возвращает ID заказа
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при создании внешнего заказа: {str(e)}")
        return None

def automate_purchases():
    """
    Автоматически создает заказы на основе плана закупок.
    """
    try:
        logger.info("Запуск автоматизации закупок...")
        
        # Получаем все планы закупок
        purchase_plans = PurchasePlan.query.all()
        logger.info(f"Найдено планов закупок: {len(purchase_plans)}")

        for plan in purchase_plans:
            logger.info(f"Обработка плана закупок: {plan.item_name} (ID: {plan.id})")
            
            # Создаем заказ во внешней системе
            external_order_id = create_external_order(plan.item_name, 1, plan.supplier)

            if external_order_id:
                # Сохраняем заказ в базе данных
                new_order = PurchaseOrder(
                    item_name=plan.item_name,
                    quantity=1,  # Пример: заказываем по 1 единице
                    supplier=plan.supplier,
                    external_order_id=external_order_id
                )
                db.session.add(new_order)
                db.session.commit()
                logger.info(f"Заказ создан для {plan.item_name} с внешним ID {external_order_id}")
            else:
                logger.error(f"Не удалось создать заказ для {plan.item_name}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка при автоматизации закупок: {str(e)}", exc_info=True)