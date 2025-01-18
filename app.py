from flask import Flask, render_template, redirect, url_for, request, flash, make_response, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from models import db, User, InventoryItem, PurchasePlan, Request, RepairRequest, PurchaseOrder, ReplacementRequest, AssignmentHistory, Report
from flask_migrate import Migrate
import csv
import io
import click
import logging
import requests
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import inspect
from sqlalchemy import text
import os
import shutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.debug = True

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.cli.command("add-user")  # добавление пользователя через flask add-user name password role
@click.argument("username")
@click.argument("password")
@click.argument("role")
def add_user(username, password, role):
    """Добавить пользователя в базу данных."""
    try:
        with app.app_context():
            
            inspector = inspect(db.engine)
            if 'user' not in inspector.get_table_names():
                
                db.create_all()
                print("Таблицы созданы.")
            
            
            user = User(username=username, password=password, role=role)
            db.session.add(user)
            db.session.commit()
            print(f"Пользователь {username} успешно добавлен.")
    except Exception as e:
        print(f"Ошибка при добавлении пользователя: {str(e)}")
        db.session.rollback()

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
        flash('У вас нет прав для выполнения этого действия', 'danger')
        return redirect(url_for('index'))
    
    try:
        user = User.query.get_or_404(user_id)
        
        
        if user.id == current_user.id:
            flash('Вы не можете удалить свой собственный аккаунт', 'danger')
            return redirect(url_for('manage_users'))
        
        
        RepairRequest.query.filter_by(user_id=user.id).delete()
        ReplacementRequest.query.filter_by(user_id=user.id).delete()
        Report.query.filter_by(user_id=user.id).delete()
        Request.query.filter_by(user_id=user.id).delete()
        AssignmentHistory.query.filter(
            (AssignmentHistory.user_id == user.id) | 
            (AssignmentHistory.admin_id == user.id)
        ).delete()
        
        
        InventoryItem.query.filter_by(assigned_to=user.id).update({
            'assigned_to': None,
            'status': 'новый'
        })
        
        
        db.session.delete(user)
        db.session.commit()
        
        flash('Пользователь успешно удален', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при удалении пользователя: {str(e)}', 'danger')
        print(f"Error in delete_user: {str(e)}")
        
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
        report_type = request.args.get('type', 'status')

        if report_type == 'status':
            broken_reports = db.session.query(
                Report,
                User.username,
                InventoryItem.name.label('item_name')
            ).join(
                User, Report.user_id == User.id
            ).join(
                InventoryItem, Report.inventory_id == InventoryItem.id
            ).filter(
                Report.report_type == 'status'
            ).order_by(
                Report.created_at.desc()
            ).all()
            
            return render_template(
                'admin/reports/status_reports.html',
                broken_reports=broken_reports
            )

        elif report_type == 'usage':
            inventory_usage = db.session.query(
                InventoryItem.id,
                InventoryItem.name,
                InventoryItem.quantity,
                InventoryItem.status,
                User.username
            ).join(
                User,
                InventoryItem.assigned_to == User.id
            ).filter(
                InventoryItem.assigned_to.isnot(None)
            ).all()
            
            return render_template('admin/reports/usage_reports.html', inventory_usage=inventory_usage)
        
        elif report_type == 'purchases':
            purchases = PurchasePlan.query.all()
            return render_template('admin/reports/purchase_reports.html', purchases=purchases)

        else:
            flash('Неизвестный тип отчета', 'error')
            return redirect(url_for('admin_dashboard'))

    except Exception as e:
        print(f"Ошибка в reports: {str(e)}")  
        flash(f'Произошла ошибка при формировании отчета: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

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

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        return redirect(url_for('admin_dashboard'))
    
    
    assigned_inventory = InventoryItem.query.filter_by(
        assigned_to=current_user.id,
        is_hidden=False
    ).all()
    
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
    
    return render_template(
        'user/dashboard.html',
        assigned_inventory=assigned_inventory,
        user_cards=user_cards
    )

@app.route('/user/view_inventory')
@login_required
def view_inventory():
    if current_user.role != 'user':
        return redirect(url_for('index'))
        
    try:
        
        available_items = InventoryItem.query.filter(
            InventoryItem.is_hidden == False,
            InventoryItem.quantity > 0,
            InventoryItem.assigned_to == None  
        ).all()
        return render_template('user/inventory.html', inventory=available_items)
    except Exception as e:
        flash(f'Произошла ошибка при загрузке инвентаря: {str(e)}', 'error')
        return redirect(url_for('user_dashboard'))

@app.route('/admin/watch_inventory')
@login_required
def watch_inventory():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    try:
        
        inventory = InventoryItem.query.filter(
            InventoryItem.is_hidden == False,
            InventoryItem.quantity > 0,
            InventoryItem.assigned_to == None  
        ).all()
        return render_template('admin/inventory.html', inventory=inventory)
    except Exception as e:
        flash(f'Произошла ошибка при загрузке инвентаря: {str(e)}', 'error')
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
        
    try:
        assigned_items = db.session.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.quantity,
            User.username
        ).join(
            User,
            InventoryItem.assigned_to == User.id
        ).filter(
            InventoryItem.assigned_to.isnot(None)
        ).all()
        
        return render_template('admin/assigned_inventory.html', assigned_items=assigned_items)
    except Exception as e:
        flash(f'Произошла ошибка при загрузке назначенного инвентаря: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

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

@app.route('/my_inventory')
@login_required
def my_inventory():
    try:
        inventory = db.session.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.quantity
        ).filter(
            InventoryItem.assigned_to == current_user.id,
            InventoryItem.is_hidden == False
        ).all()
        
        return render_template('user/my_inventory.html', inventory=inventory)
    except Exception as e:
        flash(f'Произошла ошибка при загрузке инвентаря: {str(e)}', 'error')
        return redirect(url_for('user_dashboard'))

@app.route('/return_item/<int:item_id>', methods=['POST'])
@login_required
def return_item(item_id):
    try:
        quantity = int(request.form.get('quantity', 1))
        item = InventoryItem.query.get_or_404(item_id)
        
        
        if item.assigned_to != current_user.id:
            flash('У вас нет прав на возврат этого предмета', 'error')
            return redirect(url_for('my_inventory'))
            
        if quantity > item.quantity:
            flash('Количество для возврата превышает доступное', 'error')
            return redirect(url_for('my_inventory'))
            
        if quantity == item.quantity:
            
            item.assigned_to = None
            item.status = 'новый'
        else:
            
            item.quantity -= quantity
            
            
            new_item = InventoryItem(
                name=item.name,
                quantity=quantity,
                status='новый',
                assigned_to=None
            )
            db.session.add(new_item)
            
        db.session.commit()
        flash('Инвентарь успешно возвращен', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при возврате инвентаря: {str(e)}', 'error')
        
    return redirect(url_for('my_inventory'))

def init_db():
    with app.app_context():
        
        inspector = db.inspect(db.engine)
        if 'inventory_item' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('inventory_item')]
            if 'assigned_username' not in columns:
                db.engine.execute('ALTER TABLE inventory_item ADD COLUMN assigned_username VARCHAR(80)')
        
        
        db.create_all()

@app.cli.command("reset-db")
def reset_db():
    """Полный сброс базы данных."""
    try:
        with app.app_context():
            
            db.drop_all()
            
            db.create_all()
            print("База данных успешно сброшена.")
    except Exception as e:
        print(f"Ошибка при сбросе базы данных: {str(e)}")

@app.cli.command("clean-all")
def clean_all():
    """Полная очистка базы данных и миграций."""
    try:
        
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        if os.path.exists(migrations_dir):
            shutil.rmtree(migrations_dir)
            print("Папка migrations удалена.")

        
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'inventory.db')
        if os.path.exists(db_path):
            os.remove(db_path)
            print("База данных удалена.")

        
        with app.app_context():
            db.create_all()
            print("Таблицы созданы заново.")

        print("Очистка завершена успешно.")
    except Exception as e:
        print(f"Ошибка при очистке: {str(e)}")

@app.route('/admin/unassign_item/<int:item_id>', methods=['POST'])
@login_required
def unassign_item(item_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    try:
        quantity = int(request.form.get('quantity', 1))
        item = InventoryItem.query.get_or_404(item_id)
        
        if quantity > item.quantity:
            flash('Количество для открепления превышает назначенное количество', 'error')
            return redirect(url_for('assigned_inventory'))
            
        if quantity == item.quantity:
           
            item.assigned_to = None
        else:
            
            item.quantity -= quantity
            
            
            new_item = InventoryItem(
                name=item.name,
                quantity=quantity,
                status='новый',
                assigned_to=None
            )
            db.session.add(new_item)
            
        db.session.commit()
        flash('Инвентарь успешно откреплен', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при откреплении инвентаря: {str(e)}', 'error')
        
    return redirect(url_for('assigned_inventory'))

@app.cli.command("check-db")
def check_db():
    """Проверка состояния базы данных."""
    with app.app_context():
        try:
            
            db.session.execute(text('SELECT 1'))
            print("Подключение к БД работает")
            
            
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Существующие таблицы: {tables}")
            
            
            items_count = InventoryItem.query.count()
            users_count = User.query.count()
            print(f"Количество элементов инвентаря: {items_count}")
            print(f"Количество пользователей: {users_count}")
            
            
            assigned_items = InventoryItem.query.filter(
                InventoryItem.assigned_to.isnot(None)
            ).all()
            print(f"Закрепленных элементов: {len(assigned_items)}")
            
            for item in assigned_items:
                print(f"ID: {item.id}, Название: {item.name}, "
                      f"Закреплен за: {item.assigned_username}")
                
        except Exception as e:
            print(f"Ошибка при проверке БД: {str(e)}")

@app.cli.command("add-username-column")
def add_username_column():
    """Добавление колонки assigned_username в таблицу inventory_item."""
    try:
        with app.app_context():
            
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('inventory_item')]
            
            if 'assigned_username' not in columns:
                
                with db.engine.begin() as conn:
                    conn.execute(text(
                        'ALTER TABLE inventory_item ADD COLUMN assigned_username VARCHAR(80)'
                    ))
                print("Колонка assigned_username успешно добавлена")
                
                
                items = InventoryItem.query.filter(InventoryItem.assigned_to.isnot(None)).all()
                for item in items:
                    user = User.query.get(item.assigned_to)
                    if user:
                        item.assigned_username = user.username
                db.session.commit()
                print("Значения assigned_username обновлены")
            else:
                print("Колонка assigned_username уже существует")
                
    except Exception as e:
        print(f"Ошибка при добавлении колонки: {str(e)}")
        db.session.rollback()

@app.route('/admin/assign_items', methods=['POST'])
@login_required
def assign_items():
    if current_user.role != 'admin':
        flash('У вас нет прав для выполнения этого действия', 'danger')
        return redirect(url_for('index'))
    
    try:
        user_id = request.form.get('user_id')
        item_ids = request.form.getlist('item_ids')
        
        if not user_id or not item_ids:
            flash('Не указан пользователь или элементы', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        user = User.query.get(user_id)
        if not user:
            flash('Пользователь не найден', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        for item_id in item_ids:
            item = InventoryItem.query.get(item_id)
            if item:
                item.assigned_to = user_id
                item.status = 'используемый'  
                
                
                history = AssignmentHistory(
                    item_id=item.id,
                    user_id=user_id,
                    action='assigned',
                    admin_id=current_user.id
                )
                db.session.add(history)
        
        db.session.commit()
        flash('Элементы успешно назначены', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in assign_items: {str(e)}")
        flash('Произошла ошибка при назначении элементов', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/report_broken/<int:item_id>', methods=['POST'])
@login_required
def report_broken(item_id):
    if not current_user.is_authenticated:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    try:
        item = InventoryItem.query.get_or_404(item_id)
        
        if not item:
            flash('Элемент не найден', 'danger')
            return redirect(url_for('my_inventory'))
        
        if item.assigned_to != current_user.id:
            flash('У вас нет прав для выполнения этого действия', 'danger')
            return redirect(url_for('my_inventory'))
        
        
        item.status = 'сломанный'
        
        db.session.commit()
        flash('Статус элемента изменен на "сломанный"', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in report_broken: {str(e)}")
        flash('Произошла ошибка при изменении статуса', 'danger')
    
    return redirect(url_for('my_inventory'))

@app.route('/create_report')
@login_required
def create_report_page():
    if current_user.role != 'user':
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    assigned_inventory = InventoryItem.query.filter_by(
        assigned_to=current_user.id,
        is_hidden=False
    ).all()
    
    return render_template(
        'user/create_report.html',
        assigned_inventory=assigned_inventory
    )

@app.route('/create_inventory_report', methods=['POST'])
@login_required
def create_inventory_report():
    if current_user.role != 'user':
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        inventory_id = request.form.get('inventory_id')
        quantity = int(request.form.get('quantity', 1))
        reason = request.form.get('reason')

        if not inventory_id or not reason:
            flash('Все поля должны быть заполнены', 'danger')
            return redirect(url_for('create_report_page'))

        inventory_item = InventoryItem.query.get(inventory_id)
        
        if not inventory_item or inventory_item.assigned_to != current_user.id:
            flash('Инвентарь не найден или не закреплен за вами', 'danger')
            return redirect(url_for('create_report_page'))
        
        if quantity > inventory_item.quantity:
            flash(f'Недостаточно инвентаря. Доступно: {inventory_item.quantity}', 'danger')
            return redirect(url_for('create_report_page'))

        report = Report(
            user_id=current_user.id,
            inventory_id=int(inventory_id),
            quantity=quantity,
            reason=reason,
            report_type='status',
            status='broken'
        )
        
        inventory_item.status = 'сломанный'
        
        db.session.add(report)
        db.session.commit()
        
        flash('Отчет о поломке успешно создан', 'success')
        return redirect(url_for('user_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash('Произошла ошибка при создании отчета', 'danger')
        print(f"Error: {str(e)}")
        return redirect(url_for('create_report_page'))

@app.route('/unassign_my_item/<int:item_id>', methods=['POST'])
@login_required
def unassign_my_item(item_id):
    try:
        item = InventoryItem.query.get_or_404(item_id)
        
        if item.assigned_to != current_user.id:
            flash('У вас нет прав на открепление этого предмета', 'error')
            return redirect(url_for('my_inventory'))
            
        item.assigned_to = None
        db.session.commit()
        
        flash('Инвентарь успешно откреплен', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Произошла ошибка при откреплении инвентаря: {str(e)}', 'error')
        
    return redirect(url_for('my_inventory'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)