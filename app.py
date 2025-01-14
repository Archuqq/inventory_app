from flask import Flask, render_template, redirect, url_for, request, flash, make_response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from models import db, User, InventoryItem, PurchasePlan, Request, RepairRequest, PurchaseOrder, ReplacementRequest
from flask_migrate import Migrate
import csv
import io
import click
import logging
import requests
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.debug = True

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.cli.command("add-user")  # добавление пользователя через flask add-user name password role
@click.argument("username")
@click.argument("password")
@click.argument("role")
def add_user(username, password, role):
    """Добавить пользователя в базу данных."""
    with app.app_context():
        user = User(username=username, password=password, role=role)
        db.session.add(user)
        db.session.commit()
    print(f"User {username} added successfully.")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'user'  
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Пользователь с таким именем уже существует!')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация прошла успешно! Пожалуйста, войдите в систему.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            flash('Добро пожаловать! Вы успешно вошли в систему.', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Неверные учетные данные. Пожалуйста, проверьте имя пользователя и пароль.', 'danger')
            return render_template('login.html')
            
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
        
    dashboard_cards = [
        {
            'title': 'Управление инвентарём',
            'description': 'Просмотр и редактирование инвентаря',
            'icon': 'fas fa-boxes',
            'url': url_for('watch_inventory'),
            'button_text': 'Просмотреть инвентарь'
        },
        {
            'title': 'Добавить элемент',
            'description': 'Добавление нового элемента инвентаря',
            'icon': 'fas fa-plus',
            'url': url_for('add_item'),
            'button_text': 'Добавить'
        },
        {
            'title': 'Назначить элемент',
            'description': 'Назначение элементов пользователям',
            'icon': 'fas fa-user-plus',
            'url': url_for('assign_item'),
            'button_text': 'Назначить'
        },
        {
            'title': 'Закрепленный инвентарь',
            'description': 'Просмотр назначенного инвентаря',
            'icon': 'fas fa-clipboard-list',
            'url': url_for('assigned_inventory'),
            'button_text': 'Просмотреть'
        },
        {
            'title': 'План закупок',
            'description': 'Управление планом закупок',
            'icon': 'fas fa-shopping-cart',
            'url': url_for('purchase_plan'),
            'button_text': 'Управлять'
        },
        {
            'title': 'Отчеты',
            'description': 'Просмотр отчетов и статистики',
            'icon': 'fas fa-chart-bar',
            'url': url_for('reports'),
            'button_text': 'Просмотреть отчеты'
        },
        {
            'title': 'Пользователи',
            'description': 'Управление пользователями системы',
            'icon': 'fas fa-users-cog',
            'url': url_for('manage_users'),
            'button_text': 'Управлять'
        },
        {
            'title': 'Заявки на инвентарь',
            'description': 'Просмотр и обработка заявок',
            'icon': 'fas fa-clipboard',
            'url': url_for('view_requests'),
            'button_text': 'Просмотреть заявки'
        },
        {
            'title': 'Заявки на ремонт',
            'description': 'Просмотр заявок на ремонт',
            'icon': 'fas fa-tools',
            'url': url_for('view_repair_requests'),
            'button_text': 'Просмотреть'
        }
    ]
    
    return render_template('admin/dashboard.html', dashboard_cards=dashboard_cards)

@app.route('/admin/manage_users')
@login_required
def manage_users():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin/manage_users.html', users=users)

@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
@login_required
def change_role(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    new_role = request.form['role']
    user.role = new_role
    db.session.commit()
    flash(f'Роль пользователя {user.username} изменена на {new_role}.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    if user_id == current_user.id:
        flash('Вы не можете удалить свой собственный аккаунт!', 'error')
        return redirect(url_for('manage_users'))
    
    try:
        user = User.query.get_or_404(user_id)
        
        
        Request.query.filter_by(user_id=user_id).delete()
        RepairRequest.query.filter_by(user_id=user_id).delete()
        ReplacementRequest.query.filter_by(user_id=user_id).delete()
        
        
        assigned_items = InventoryItem.query.filter_by(assigned_to=user_id).all()
        
        for assigned_item in assigned_items:
            
            existing_item = InventoryItem.query.filter_by(
                name=assigned_item.name,
                assigned_to=None,
                is_hidden=False
            ).first()
            
            if existing_item:
                
                existing_item.quantity += assigned_item.quantity
                
                db.session.delete(assigned_item)
            else:
                
                assigned_item.assigned_to = None
                assigned_item.is_hidden = False
        
        
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Пользователь {user.username} успешно удален.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении пользователя: {str(e)}', 'error')
    
    return redirect(url_for('manage_users'))

@app.route('/admin/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        status = request.form['status']
        
        existing_item = InventoryItem.query.filter_by(name=name).first()
        
        if existing_item:
            flash(f'Элемент "{name}" уже существует в инвентаре. Количество не изменено.', 'info')
        else:
            new_item = InventoryItem(
                name=name,
                quantity=quantity,
                status=status,
                is_added_by_admin=True
            )
            db.session.add(new_item)
            db.session.commit()
            flash(f'Элемент "{name}" успешно добавлен в инвентарь.', 'success')
        
        return redirect(url_for('watch_inventory'))
    
    return render_template('admin/add_item.html')

@app.route('/admin/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    item = InventoryItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.name = request.form['name']
        item.quantity = request.form['quantity']
        item.status = request.form['status']
        db.session.commit()
        flash('Элемент успешно обновлён!', 'success')
        return redirect(url_for('watch_inventory'))
    
    return render_template('admin/edit_item.html', item=item)

@app.route('/admin/assign_item', methods=['GET', 'POST'])
@login_required
def assign_item():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    users = User.query.all()
    inventory = InventoryItem.query.filter(
        InventoryItem.assigned_to == None,
        InventoryItem.quantity > 0
    ).all()
    
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        user_id = request.form.get('user_id')
        quantity = int(request.form.get('quantity', 0))
        
        item = InventoryItem.query.get(item_id)
        if not item:
            flash('Элемент не найден!', 'error')
            return redirect(url_for('assign_item'))
        
        if quantity <= 0:
            flash('Количество должно быть больше нуля!', 'error')
            return redirect(url_for('assign_item'))
        
        if item.quantity < quantity:
            flash('Недостаточно элементов в инвентаре!', 'error')
            return redirect(url_for('assign_item'))
        
        
        item.quantity -= quantity
        
        
        user_inventory = InventoryItem.query.filter_by(
            assigned_to=user_id,
            name=item.name
        ).first()
        
        if user_inventory:
            
            user_inventory.quantity += quantity
        else:
            
            new_user_item = InventoryItem(
                name=item.name,
                quantity=quantity,
                status=item.status,
                assigned_to=user_id,
                is_added_by_admin=False
            )
            db.session.add(new_user_item)
        
        try:
            db.session.commit()
            flash(f'Элемент успешно назначен!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при назначении элемента: {str(e)}', 'error')
        
        return redirect(url_for('assign_item'))
    
    return render_template('admin/assign_item.html', users=users, inventory=inventory)

@app.route('/admin/purchase_plan', methods=['GET', 'POST'])
@login_required
def purchase_plan():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            item_name = request.form['item_name']
            price = float(request.form['price'])
            supplier = request.form['supplier']
            
            new_plan = PurchasePlan(
                item_name=item_name,
                price=price,
                supplier=supplier,
                status='активен'
            )
            db.session.add(new_plan)
            db.session.commit()
            flash('План закупки успешно добавлен!', 'success')
            return redirect(url_for('reports', type='purchases', status='all'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении плана: {str(e)}', 'error')
            return redirect(url_for('purchase_plan'))

    
    purchase_plans = PurchasePlan.query.all()
    return render_template('admin/purchase_plan.html', purchase_plans=purchase_plans)

@app.route('/admin/delete_purchase_plan/<int:plan_id>')
@login_required
def delete_purchase_plan(plan_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    try:
        plan = PurchasePlan.query.get_or_404(plan_id)
        db.session.delete(plan)
        db.session.commit()
        flash('План закупки удален!', 'success')
        return redirect(url_for('reports', type='purchases', status='all'))
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении плана: {str(e)}', 'error')
        return redirect(url_for('reports', type='purchases', status='all'))

@app.route('/admin/reports')
@login_required
def reports():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        report_type = request.args.get('type', 'usage')
        filter_status = request.args.get('status', 'all')
        filter_supplier = request.args.get('supplier', 'all')

        if report_type in ['usage', 'inventory_usage']:
            
            query = db.session.query(
                InventoryItem.id,
                InventoryItem.name,
                InventoryItem.quantity,
                InventoryItem.status,
                InventoryItem.assigned_to,
                User.username
            ).outerjoin(
                User,
                InventoryItem.assigned_to == User.id
            ).filter(
                InventoryItem.assigned_to.isnot(None)
            )

            if filter_status != 'all':
                query = query.filter(InventoryItem.status == filter_status)

            inventory_usage = query.all()
            
            
            inventory_usage_display = []
            for item in inventory_usage:
                username = item.username if item.username else 'Удалённый пользователь'
                
                inventory_usage_display.append({
                    'id': item.id,
                    'name': item.name,
                    'quantity': item.quantity,
                    'status': item.status,
                    'assigned_to': item.assigned_to,
                    'username': username
                })
            
            return render_template(
                'admin/reports.html',
                report_type='usage',
                inventory_usage=inventory_usage_display,
                filter_status=filter_status
            )
        
        elif report_type in ['status', 'inventory_status']:
            inventory_status = InventoryItem.query.filter(
                InventoryItem.is_hidden == False
            ).all()
            
            return render_template(
                'admin/reports.html',
                report_type='status',
                inventory_status=inventory_status,
                filter_status=filter_status
            )
        
        elif report_type in ['purchases', 'purchase_plan']:
            purchase_plans = PurchasePlan.query.all()
            suppliers = db.session.query(PurchasePlan.supplier).distinct().all()
            suppliers = [supplier[0] for supplier in suppliers]
            
            return render_template(
                'admin/reports.html',
                report_type='purchases',
                purchases=purchase_plans,
                suppliers=suppliers,
                filter_supplier=filter_supplier,
                filter_status=filter_status
            )
        
        else:
            flash('Неизвестный тип отчета', 'error')
            return redirect(url_for('admin_dashboard'))

    except Exception as e:
        print(f"Ошибка в reports: {str(e)}")  
        flash(f'Произошла ошибка при формировании отчета: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/reports/export')
@login_required
def export_reports():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    report_type = request.args.get('type', 'usage')
    filter_status = request.args.get('status', 'all')
    filter_supplier = request.args.get('supplier', 'all')

    
    if report_type == 'usage':
        inventory = InventoryItem.query.all()
        if filter_status != 'all':
            inventory = InventoryItem.query.filter_by(status=filter_status).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Название', 'Количество', 'Статус', 'Назначено пользователю'])
        for item in inventory:
            writer.writerow([item.id, item.name, item.quantity, item.status, item.assigned_to])

    
    elif report_type == 'status':
        inventory = InventoryItem.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Название', 'Количество', 'Статус'])
        for item in inventory:
            writer.writerow([item.id, item.name, item.quantity, item.status])

   
    elif report_type == 'purchases':
        purchases = PurchasePlan.query.all()
        if filter_supplier != 'all':
            purchases = PurchasePlan.query.filter_by(supplier=filter_supplier).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Название', 'Цена', 'Поставщик'])
        for purchase in purchases:
            writer.writerow([purchase.id, purchase.item_name, purchase.price, purchase.supplier])

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'admin':
        user_cards = [
            {
                'title': 'Просмотр инвентаря',
                'description': 'Просмотр доступного инвентаря',
                'icon': 'fas fa-boxes',
                'url': url_for('view_inventory'),
                'button_text': 'Просмотреть'
            },
            {
                'title': 'Мой инвентарь',
                'description': 'Просмотр закрепленного инвентаря',
                'icon': 'fas fa-clipboard-list',
                'url': url_for('my_inventory'),
                'button_text': 'Просмотреть'
            },
            {
                'title': 'Запросить элемент',
                'description': 'Создание заявки на получение инвентаря',
                'icon': 'fas fa-hand-pointer',
                'url': url_for('request_item'),
                'button_text': 'Запросить'
            },
            {
                'title': 'Запросить ремонт',
                'description': 'Создание заявки на ремонт',
                'icon': 'fas fa-wrench',
                'url': url_for('repair_request'),
                'button_text': 'Запросить ремонт'
            },
            {
                'title': 'Запросить замену',
                'description': 'Создание заявки на замену',
                'icon': 'fas fa-exchange-alt',
                'url': url_for('replacement_request'),
                'button_text': 'Запросить замену'
            },
            {
                'title': 'Статус заявок',
                'description': 'Просмотр статуса ваших заявок',
                'icon': 'fas fa-clipboard-check',
                'url': url_for('request_status'),
                'button_text': 'Просмотреть статус'
            }
        ]
        return render_template('user/dashboard.html', user_cards=user_cards)

@app.route('/user/view_inventory')
@login_required
def view_inventory():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    
    try:
        
        items_to_hide = InventoryItem.query.filter(
            InventoryItem.quantity <= 0,
            InventoryItem.is_hidden == False
        ).all()
        
        for item in items_to_hide:
            item.is_hidden = True
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении элементов: {str(e)}', 'error')
        
        
        inventory = InventoryItem.query.filter(
            InventoryItem.is_hidden == False,
            InventoryItem.quantity > 0,
            InventoryItem.assigned_to == None  
        ).all()
        
        return render_template('user/inventory.html', inventory=inventory)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка: {str(e)}', 'error')
        return redirect(url_for('user_dashboard'))

@app.route('/admin/watch_inventory')
@login_required
def watch_inventory():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    try:
        
        items_to_hide = InventoryItem.query.filter(
            InventoryItem.quantity <= 0,
            InventoryItem.is_hidden == False
        ).all()
        
        for item in items_to_hide:
            item.is_hidden = True
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении элементов: {str(e)}', 'error')
        
        
        inventory = InventoryItem.query.filter(
            InventoryItem.is_hidden == False,
            InventoryItem.assigned_to == None,
            InventoryItem.quantity > 0
        ).all()
        
        return render_template('admin/inventory.html', inventory=inventory)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/user/request_item', methods=['GET', 'POST'])
@login_required
def request_item():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    
    
    selected_item_id = request.args.get('item_id', type=int)
    
    
    inventory = InventoryItem.query.filter(
        InventoryItem.is_hidden == False,
        InventoryItem.quantity > 0,
        InventoryItem.assigned_to == None
    ).all()
    
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        quantity = request.form.get('quantity')
        
        if not item_id or not quantity:
            flash('Пожалуйста, заполните все поля', 'error')
            return redirect(url_for('request_item'))
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                flash('Количество должно быть больше нуля', 'error')
                return redirect(url_for('request_item'))
            
            item = InventoryItem.query.get(item_id)
            if not item:
                flash('Элемент не найден', 'error')
                return redirect(url_for('request_item'))
            
            if item.quantity < quantity:
                flash('Запрошенное количество превышает доступное', 'error')
                return redirect(url_for('request_item'))
            
            new_request = Request(
                item_id=item_id,
                quantity=quantity,
                status='ожидает',
                user_id=current_user.id
            )
            
            db.session.add(new_request)
            db.session.commit()
            
            flash('Заявка успешно создана!', 'success')
            return redirect(url_for('request_status'))
            
        except ValueError:
            flash('Некорректное значение количества', 'error')
            return redirect(url_for('request_item'))
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка: {str(e)}', 'error')
            return redirect(url_for('request_item'))
    
    return render_template('user/request_item.html', 
                         inventory=inventory, 
                         selected_item_id=selected_item_id)

@app.route('/user/request_status')
@login_required
def request_status():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    
    request_type = request.args.get('request_type', 'all')
    
    if request_type == 'inventory':
        requests = db.session.query(
            Request.id,
            Request.item_id,
            Request.quantity,
            Request.status,
            InventoryItem.name.label('item_name')
        ).join(
            InventoryItem, Request.item_id == InventoryItem.id
        ).filter(
            Request.user_id == current_user.id
        ).all()
        
        
        requests = [{
            "id": req.id,
            "item_id": req.item_id,
            "quantity": req.quantity,
            "status": req.status,
            "item_name": req.item_name,
            "type": "inventory"  
        } for req in requests]
        
    elif request_type == 'repair':
        requests = db.session.query(
            RepairRequest.id,
            RepairRequest.item_id,
            RepairRequest.description,
            RepairRequest.status,
            InventoryItem.name.label('item_name')
        ).join(
            InventoryItem, RepairRequest.item_id == InventoryItem.id
        ).filter(
            RepairRequest.user_id == current_user.id
        ).all()
        
        
        requests = [{
            "id": req.id,
            "item_id": req.item_id,
            "description": req.description,
            "status": req.status,
            "item_name": req.item_name,
            "type": "repair",  
            "quantity": None  
        } for req in requests]
        
    elif request_type == 'replacement':
        requests = db.session.query(
            ReplacementRequest.id,
            ReplacementRequest.item_id,
            ReplacementRequest.quantity,
            ReplacementRequest.reason,
            ReplacementRequest.status,
            InventoryItem.name.label('item_name')
        ).join(
            InventoryItem, ReplacementRequest.item_id == InventoryItem.id
        ).filter(
            ReplacementRequest.user_id == current_user.id
        ).all()
        
       
        requests = [{
            "id": req.id,
            "item_id": req.item_id,
            "quantity": req.quantity,
            "reason": req.reason,
            "status": req.status,
            "item_name": req.item_name,
            "type": "replacement"  
        } for req in requests]
        
    else:
        
        inventory_requests = db.session.query(
            Request.id,
            Request.item_id,
            Request.quantity,
            Request.status,
            InventoryItem.name.label('item_name')
        ).join(
            InventoryItem, Request.item_id == InventoryItem.id
        ).filter(
            Request.user_id == current_user.id
        ).all()
        
        repair_requests = db.session.query(
            RepairRequest.id,
            RepairRequest.item_id,
            RepairRequest.description,
            RepairRequest.status,
            InventoryItem.name.label('item_name')
        ).join(
            InventoryItem, RepairRequest.item_id == InventoryItem.id
        ).filter(
            RepairRequest.user_id == current_user.id
        ).all()
        
        replacement_requests = db.session.query(
            ReplacementRequest.id,
            ReplacementRequest.item_id,
            ReplacementRequest.quantity,
            ReplacementRequest.reason,
            ReplacementRequest.status,
            InventoryItem.name.label('item_name')
        ).join(
            InventoryItem, ReplacementRequest.item_id == InventoryItem.id
        ).filter(
            ReplacementRequest.user_id == current_user.id
        ).all()
        
        
        requests = []
        for req in inventory_requests:
            requests.append({
                "id": req.id,
                "item_id": req.item_id,
                "quantity": req.quantity,
                "status": req.status,
                "item_name": req.item_name,
                "type": "inventory"  
            })
        for req in repair_requests:
            requests.append({
                "id": req.id,
                "item_id": req.item_id,
                "quantity": None,  
                "status": req.status,
                "item_name": req.item_name,
                "type": "repair",  
                "description": req.description  
            })
        for req in replacement_requests:
            requests.append({
                "id": req.id,
                "item_id": req.item_id,
                "quantity": req.quantity,
                "status": req.status,
                "item_name": req.item_name,
                "type": "replacement",  
                "reason": req.reason  
            })
    
    return render_template('user/request_status.html', requests=requests, selected_request_type=request_type)

@app.route('/user/repair_request', methods=['GET', 'POST'])
@login_required
def repair_request():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    
    inventory = InventoryItem.query.filter(
        InventoryItem.assigned_to == current_user.id,  
        InventoryItem.quantity > 0  
    ).all()
    
    if request.method == 'POST':
        try:
            item_id = request.form['item_id']
            description = request.form['description']
            user_id = current_user.id

            item = InventoryItem.query.get(item_id)
            if not item:
                flash('Элемент инвентаря не найден!', 'error')
                return redirect(url_for('repair_request'))

            new_repair_request = RepairRequest(
                item_id=item_id,
                description=description,
                user_id=user_id,
                status='ожидание'
            )
            db.session.add(new_repair_request)
            db.session.commit()
            flash('Заявка на ремонт успешно отправлена!', 'success')
            return redirect(url_for('request_status', request_type='repair'))
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in repair_request: {str(e)}", exc_info=True)
            flash(f'Произошла ошибка: {str(e)}', 'error')
            return redirect(url_for('repair_request'))
    
    return render_template('user/repair_request.html', inventory=inventory)

@app.route('/user/repair_status')
@login_required
def repair_status():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    repair_requests = RepairRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('user/repair_status.html', repair_requests=repair_requests)

def create_external_order(item_name, quantity, supplier):
    """
    Отправляет заказ внешнему поставщику через API.
    Возвращает ID заказа во внешней системе.
    """
    api_url = "https://api.supplier.com/orders"  # Заменить на URL API
    payload = {
        "item_name": item_name,
        "quantity": quantity,
        "supplier": supplier
    }
    headers = {
        "Authorization": "Bearer YOUR_API_KEY",  # Заменить на API-ключ
        "Content-Type": "application/json"
    }

    try:
        logger.info(f"Отправка запроса к API: {api_url}")
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status() 
        order_data = response.json()
        logger.info(f"Ответ от API: {order_data}")
        return order_data.get("order_id")  
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при создании внешнего заказа: {str(e)}")
        return None

def automate_purchases():
    with app.app_context():
        try:
            
            items = InventoryItem.query.all()
            
            for item in items:
                
                if item.quantity < 10:  
                    
                    existing_plan = PurchasePlan.query.filter_by(
                        item_id=item.id,
                        status='активен'
                    ).first()
                    
                    if not existing_plan:
                        
                        new_plan = PurchasePlan(
                            item_id=item.id,
                            quantity=20,  
                            status='активен'
                        )
                        db.session.add(new_plan)
                        logger.info(f'Created purchase plan for item {item.name}')
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error in automate_purchases: {str(e)}", exc_info=True)
            db.session.rollback()

@app.route('/admin/automate_purchases', methods=['POST'])
@login_required
def run_automate_purchases():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'error')
        return redirect(url_for('index'))
    
    try:
        automate_purchases()
        flash('Автоматизация закупок успешно запущена!', 'success')
    except Exception as e:
        flash(f'Произошла ошибка: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/view_requests')
@login_required
def view_requests():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    requests = db.session.query(
        Request.id.label('request_id'),  
        Request.item_id,               
        Request.quantity,               
        Request.status,                 
        User.username,                 
        User.id.label('user_id'),       
        InventoryItem.name.label('item_name')  
    ).join(
        User, Request.user_id == User.id  
    ).outerjoin(
        InventoryItem, Request.item_id == InventoryItem.id  
    ).all()
    
    return render_template('admin/view_requests.html', requests=requests)

@app.route('/admin/approve_request/<int:request_id>', methods=['POST'])
@login_required
def approve_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    req = Request.query.get_or_404(request_id)
    req.status = 'одобрено'
    db.session.commit()
    flash('Заявка одобрена!', 'success')
    return redirect(url_for('view_requests'))

@app.route('/admin/reject_request/<int:request_id>', methods=['POST'])
@login_required
def reject_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    req = Request.query.get_or_404(request_id)
    req.status = 'отклонено'
    db.session.commit()
    flash('Заявка отклонена!', 'error')
    return redirect(url_for('view_requests'))

@app.route('/admin/view_repair_requests')
@login_required
def view_repair_requests():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    repair_requests = db.session.query(
        RepairRequest.id.label('repair_request_id'),
        RepairRequest.description,
        RepairRequest.status,
        User.username,
        User.id.label('user_id'),
        InventoryItem.name.label('item_name'),
        InventoryItem.id.label('item_id')  
    ).join(
        User, RepairRequest.user_id == User.id
    ).join(
        InventoryItem, RepairRequest.item_id == InventoryItem.id
    ).all()
    
    return render_template('admin/view_repair_requests.html', repair_requests=repair_requests)

@app.route('/admin/approve_repair_request/<int:request_id>', methods=['POST'])
@login_required
def approve_repair_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    repair_request = RepairRequest.query.get_or_404(request_id)
    repair_request.status = 'одобрено'
    db.session.commit()
    flash('Заявка на ремонт одобрена!', 'success')
    return redirect(url_for('view_repair_requests'))

@app.route('/admin/reject_repair_request/<int:request_id>', methods=['POST'])
@login_required
def reject_repair_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    repair_request = RepairRequest.query.get_or_404(request_id)
    repair_request.status = 'отклонено'
    db.session.commit()
    flash('Заявка на ремонт отклонена!', 'error')
    return redirect(url_for('view_repair_requests'))

@app.route('/admin/assigned_inventory')
@login_required
def assigned_inventory():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    assigned_items = db.session.query(
        InventoryItem.id,
        InventoryItem.name,
        InventoryItem.quantity,
        InventoryItem.status,
        User.id.label('user_id'),  
        User.username
    ).join(User, InventoryItem.assigned_to == User.id).all()

    return render_template('admin/assigned_inventory.html', assigned_items=assigned_items)

@app.route('/user/replacement_request', methods=['GET', 'POST'])
@login_required
def replacement_request():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    
    inventory = InventoryItem.query.filter(
        InventoryItem.assigned_to == current_user.id,
        InventoryItem.quantity > 0
    ).all()
    
    if request.method == 'POST':
        try:
            item_id = request.form['item_id']
            reason = request.form['reason']
            quantity = request.form.get('quantity', 1)  
            
            item = InventoryItem.query.get(item_id)
            if not item:
                flash('Элемент инвентаря не найден!', 'error')
                return redirect(url_for('replacement_request'))
            
            
            if int(quantity) > item.quantity:
                flash(f'Недостаточно элементов. Доступно: {item.quantity}', 'error')
                return redirect(url_for('replacement_request'))
            
            new_request = ReplacementRequest(
                item_id=item_id,
                user_id=current_user.id,
                reason=reason,
                status='ожидание',
                quantity=quantity  
            )
            db.session.add(new_request)
            db.session.commit()
            
            flash('Заявка на замену успешно отправлена!', 'success')
            return redirect(url_for('request_status', request_type='replacement'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in replacement_request: {str(e)}", exc_info=True)
            flash('Произошла ошибка при создании заявки. Пожалуйста, попробуйте снова.', 'error')
            return redirect(url_for('replacement_request'))
    
    return render_template('user/replacement_request.html', inventory=inventory)

@app.route('/admin/view_replacement_requests')
@login_required
def view_replacement_requests():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    replacement_requests = db.session.query(
        ReplacementRequest,
        User.username,
        InventoryItem.name.label('item_name'),
        InventoryItem.id.label('item_id')
    ).join(
        User, ReplacementRequest.user_id == User.id
    ).join(
        InventoryItem, ReplacementRequest.item_id == InventoryItem.id
    ).all()
    
    return render_template('admin/view_replacement_requests.html', replacement_requests=replacement_requests)

@app.route('/admin/approve_replacement_request/<int:request_id>', methods=['POST'])
@login_required
def approve_replacement_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    replacement_request = ReplacementRequest.query.get_or_404(request_id)
    replacement_request.status = 'одобрено'
    db.session.commit()
    
    flash('Заявка на замену одобрена!', 'success')
    return redirect(url_for('view_replacement_requests'))

@app.route('/admin/reject_replacement_request/<int:request_id>', methods=['POST'])
@login_required
def reject_replacement_request(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    replacement_request = ReplacementRequest.query.get_or_404(request_id)
    replacement_request.status = 'отклонено'
    db.session.commit()
    
    flash('Заявка на замену отклонена!', 'error')
    return redirect(url_for('view_replacement_requests'))

@app.route('/admin/hide_item/<int:item_id>', methods=['POST'])
@login_required
def hide_item(item_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    item = InventoryItem.query.get_or_404(item_id)
    item.is_hidden = True
    db.session.commit()
    
    flash(f'Элемент "{item.name}" скрыт из списка.', 'success')
    return redirect(url_for('watch_inventory'))

@app.route('/admin/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    try:
        item = InventoryItem.query.get_or_404(item_id)
        
        
        Request.query.filter_by(item_id=item_id).delete()
        RepairRequest.query.filter_by(item_id=item_id).delete()
        ReplacementRequest.query.filter_by(item_id=item_id).delete()
        
        
        db.session.delete(item)
        db.session.commit()
        
        flash(f'Элемент "{item.name}" успешно удален из базы данных.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении элемента: {str(e)}', 'error')
    
    return redirect(url_for('watch_inventory'))

@app.route('/user/my_inventory')
@login_required
def my_inventory():
    if current_user.role != 'user':
        return redirect(url_for('index'))
    
    
    inventory = InventoryItem.query.filter_by(
        assigned_to=current_user.id,
        is_hidden=False
    ).all()
    
    return render_template('user/my_inventory.html', inventory=inventory)

def init_db():
    with app.app_context():
        
        inspector = db.inspect(db.engine)
        if 'inventory_item' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('inventory_item')]
            if 'assigned_username' not in columns:
                db.engine.execute('ALTER TABLE inventory_item ADD COLUMN assigned_username VARCHAR(80)')
        
        
        db.create_all()


if __name__ == '__main__':
    init_db()
    app.run(debug=True)