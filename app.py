import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'expenses.db')
app.secret_key = 'change-this-secret'  # change in production


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL
        )
    ''')
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/', methods=['GET'])
def index():
    db = get_db()

    # Filters from query params (so filter form can submit GET)
    start = request.args.get('start', '').strip()
    end = request.args.get('end', '').strip()
    category = request.args.get('category', 'All').strip()

    # Build SQL with optional where clauses
    where_clauses = []
    params = []

    if start:
        where_clauses.append("date >= ?")
        params.append(start)
    if end:
        where_clauses.append("date <= ?")
        params.append(end)
    if category and category != 'All':
        where_clauses.append("category = ?")
        params.append(category)

    where_sql = ''
    if where_clauses:
        where_sql = 'WHERE ' + ' AND '.join(where_clauses)

    query = f"SELECT * FROM expenses {where_sql} ORDER BY date DESC, id DESC"
    cur = db.execute(query, params)
    expenses = cur.fetchall()

    # Total for filtered results
    total = sum([row['amount'] for row in expenses]) if expenses else 0.0

    # Distinct categories for dropdown
    cur2 = db.execute("SELECT DISTINCT category FROM expenses ORDER BY category")
    categories = [r['category'] for r in cur2.fetchall()]

    # Aggregations for charts (group by category and date)
    category_totals = {}
    date_totals = {}
    for row in expenses:
        cat = row['category'] or 'Uncategorized'
        category_totals[cat] = category_totals.get(cat, 0.0) + float(row['amount'])
        d = row['date']
        date_totals[d] = date_totals.get(d, 0.0) + float(row['amount'])

    # Prepare lists for Chart.js (pass Python lists to the template)
    category_labels = list(category_totals.keys())
    category_values = [round(v, 2) for v in category_totals.values()]

    # Sort dates ascending for the time chart
    date_items = sorted(date_totals.items())
    date_labels = [d for d, _ in date_items]
    date_values = [round(v, 2) for _, v in date_items]

    return render_template(
        'index.html',
        expenses=expenses,
        total=total,
        categories=categories,
        selected_category=category,
        start=start,
        end=end,
        category_labels=category_labels,
        category_values=category_values,
        date_labels=date_labels,
        date_values=date_values,
    )


@app.route('/add', methods=['POST'])
def add():
    amount = request.form.get('amount')
    category = request.form.get('category')
    description = request.form.get('description')
    date = request.form.get('date')

    # Basic validation
    if not amount or not category or not date:
        return redirect(url_for('index'))

    try:
        amount_val = float(amount)
    except ValueError:
        return redirect(url_for('index'))

    db = get_db()
    db.execute(
        'INSERT INTO expenses (amount, category, description, date) VALUES (?, ?, ?, ?)',
        (amount_val, category, description, date)
    )
    db.commit()
    return redirect(url_for('index'))


@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit(expense_id):
    db = get_db()

    if request.method == 'POST':
        amount = request.form.get('amount')
        category = request.form.get('category')
        description = request.form.get('description')
        date = request.form.get('date')

        if not amount or not category or not date:
            return redirect(url_for('edit', expense_id=expense_id))

        try:
            amount_val = float(amount)
        except ValueError:
            return redirect(url_for('edit', expense_id=expense_id))

        db.execute(
            'UPDATE expenses SET amount = ?, category = ?, description = ?, date = ? WHERE id = ?',
            (amount_val, category, description, date, expense_id)
        )
        db.commit()
        return redirect(url_for('index'))
    else:
        cur = db.execute('SELECT * FROM expenses WHERE id = ?', (expense_id,))
        expense = cur.fetchone()
        if expense is None:
            return redirect(url_for('index'))
        return render_template('edit.html', expense=expense)


@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete(expense_id):
    db = get_db()
    db.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    db.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    # Ensure DB exists and table is created before first request
    with app.app_context():
        init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)