import os
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from datetime import datetime
import sqlite3

# Get PostgreSQL connection details from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

# Check if we should use SQLite as fallback (for development)
USE_SQLITE = DATABASE_URL is None

def initialize_database():
    """
    Initialize the database with the required tables if they don't exist.
    """
    if USE_SQLITE:
        # SQLite initialization
        conn = sqlite3.connect('portfolio.db')
        cursor = conn.cursor()
        
        # Create assets table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            avg_buy_price REAL DEFAULT 0,
            current_price REAL DEFAULT 0,
            last_updated TIMESTAMP,
            UNIQUE(asset_name)
        )
        ''')
        
        # Create trades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TIMESTAMP NOT NULL,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            total_amount REAL NOT NULL,
            profit_loss REAL DEFAULT 0,
            related_trade_id INTEGER DEFAULT NULL,
            trade_category TEXT DEFAULT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create cash_balance table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS cash_balance (
            id INTEGER PRIMARY KEY,
            amount_irr REAL DEFAULT 0,
            amount_usd REAL DEFAULT 0,
            last_updated TIMESTAMP
        )
        ''')
        
        
        # Initialize cash balance if not exists
        cursor.execute('SELECT COUNT(*) FROM cash_balance')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO cash_balance (id, amount_irr, amount_usd, last_updated) VALUES (1, 0, 0, ?)', 
                          (datetime.now(),))
        
        conn.commit()
        conn.close()
    else:
        try:
            # PostgreSQL initialization
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            conn.commit()
            
            # Check if cash_balance is initialized
            cursor.execute('SELECT COUNT(*) FROM cash_balance')
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO cash_balance (id, amount_irr, amount_usd, last_updated) VALUES (1, 0, 0, %s)',
                              (datetime.now(),))
                conn.commit()
                
            conn.close()
        except Exception as e:
            print(f"Error initializing PostgreSQL database: {e}")

def update_database_schema():
    """
    Update database schema with new columns for existing tables.
    This function should be called after initialize_database.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if USE_SQLITE:
            # Check if columns exist in trades table
            cursor.execute("PRAGMA table_info(trades)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add new columns if they don't exist
            if 'related_trade_id' not in columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN related_trade_id INTEGER DEFAULT NULL')
            if 'trade_category' not in columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN trade_category TEXT DEFAULT NULL')
            if 'is_profit_sale' not in columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN is_profit_sale BOOLEAN DEFAULT 0')
            if 'currency' not in columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN currency TEXT DEFAULT "تومان"')
        else:
            # PostgreSQL version
            # Check if related_trade_id column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = 'related_trade_id'
            """)
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE trades ADD COLUMN related_trade_id INTEGER DEFAULT NULL')
                
            # Check if trade_category column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = 'trade_category'
            """)
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE trades ADD COLUMN trade_category TEXT DEFAULT NULL')
                
            # Check if is_profit_sale column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = 'is_profit_sale'
            """)
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE trades ADD COLUMN is_profit_sale BOOLEAN DEFAULT FALSE')
                
            # Check if currency column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = 'currency'
            """)
            if cursor.fetchone() is None:
                cursor.execute('ALTER TABLE trades ADD COLUMN currency TEXT DEFAULT \'تومان\'')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating database schema: {e}")
        return False

def get_connection():
    """
    Get a connection to the database.
    
    Returns:
        Connection: A database connection (PostgreSQL or SQLite)
    """
    if USE_SQLITE:
        return sqlite3.connect('portfolio.db')
    else:
        # Connect to PostgreSQL
        return psycopg2.connect(DATABASE_URL)

def update_asset_after_trade(asset_name, asset_type, quantity, price, trade_type):
    """
    Update asset information after a trade is recorded.
    
    Args:
        asset_name (str): Name of the asset
        asset_type (str): Type of the asset
        quantity (float): Quantity traded
        price (float): Price of the trade
        trade_type (str): Type of trade (خرید/فروش)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if USE_SQLITE:
            # SQLite version
            # Check if asset exists
            cursor.execute('SELECT * FROM assets WHERE asset_name = ?', (asset_name,))
            asset = cursor.fetchone()
            
            if trade_type == 'خرید':
                if asset:
                    # Asset exists, update it
                    current_quantity = asset[3]
                    current_avg_price = asset[4]
                    
                    # Calculate new average price and quantity
                    new_quantity = current_quantity + quantity
                    if new_quantity > 0:
                        new_avg_price = ((current_quantity * current_avg_price) + (quantity * price)) / new_quantity
                    else:
                        new_avg_price = price
                    
                    cursor.execute('''
                        UPDATE assets 
                        SET quantity = ?, avg_buy_price = ?, current_price = ?, last_updated = ? 
                        WHERE asset_name = ?
                    ''', (new_quantity, new_avg_price, price, datetime.now(), asset_name))
                else:
                    # New asset, insert it
                    cursor.execute('''
                        INSERT INTO assets (asset_name, asset_type, quantity, avg_buy_price, current_price, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (asset_name, asset_type, quantity, price, price, datetime.now()))
            elif trade_type == 'فروش':
                if asset:
                    # Update quantity after sell
                    new_quantity = asset[3] - quantity
                    
                    # Keep the average buy price the same
                    cursor.execute('''
                        UPDATE assets 
                        SET quantity = ?, current_price = ?, last_updated = ? 
                        WHERE asset_name = ?
                    ''', (new_quantity, price, datetime.now(), asset_name))
                    
                    # If quantity is zero, optionally delete the asset
                    if new_quantity <= 0:
                        pass  # We'll keep the asset with zero quantity for history
                else:
                    # Shouldn't happen, but handle it anyway
                    cursor.execute('''
                        INSERT INTO assets (asset_name, asset_type, quantity, avg_buy_price, current_price, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (asset_name, asset_type, -quantity, price, price, datetime.now()))
        else:
            # PostgreSQL version
            # Check if asset exists
            cursor.execute('SELECT * FROM assets WHERE asset_name = %s', (asset_name,))
            asset = cursor.fetchone()
            
            if trade_type == 'خرید':
                if asset:
                    # Asset exists, update it
                    current_quantity = asset[3]
                    current_avg_price = asset[4]
                    
                    # Calculate new average price and quantity
                    new_quantity = current_quantity + quantity
                    if new_quantity > 0:
                        new_avg_price = ((current_quantity * current_avg_price) + (quantity * price)) / new_quantity
                    else:
                        new_avg_price = price
                    
                    cursor.execute('''
                        UPDATE assets 
                        SET quantity = %s, avg_buy_price = %s, current_price = %s, last_updated = %s 
                        WHERE asset_name = %s
                    ''', (new_quantity, new_avg_price, price, datetime.now(), asset_name))
                else:
                    # New asset, insert it
                    cursor.execute('''
                        INSERT INTO assets (asset_name, asset_type, quantity, avg_buy_price, current_price, last_updated)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (asset_name, asset_type, quantity, price, price, datetime.now()))
            elif trade_type == 'فروش':
                if asset:
                    # Update quantity after sell
                    new_quantity = asset[3] - quantity
                    
                    # Keep the average buy price the same
                    cursor.execute('''
                        UPDATE assets 
                        SET quantity = %s, current_price = %s, last_updated = %s 
                        WHERE asset_name = %s
                    ''', (new_quantity, price, datetime.now(), asset_name))
                    
                    # If quantity is zero, optionally delete the asset
                    if new_quantity <= 0:
                        pass  # We'll keep the asset with zero quantity for history
                else:
                    # Shouldn't happen, but handle it anyway
                    cursor.execute('''
                        INSERT INTO assets (asset_name, asset_type, quantity, avg_buy_price, current_price, last_updated)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (asset_name, asset_type, -quantity, price, price, datetime.now()))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating asset: {e}")
        return False

def update_cash_balance(amount, is_deposit=True):
    """
    Update cash balance.
    
    Args:
        amount (float): Amount to add or subtract
        is_deposit (bool): True for deposit, False for withdrawal
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if USE_SQLITE:
        # SQLite version
        cursor.execute('SELECT amount_irr FROM cash_balance WHERE id = 1')
        current_balance = cursor.fetchone()[0]
        
        if is_deposit:
            new_balance = current_balance + amount
        else:
            new_balance = current_balance - amount
        
        cursor.execute('''
            UPDATE cash_balance 
            SET amount_irr = ?, last_updated = ? 
            WHERE id = 1
        ''', (new_balance, datetime.now()))
    else:
        # PostgreSQL version
        cursor.execute('SELECT amount_irr FROM cash_balance WHERE id = 1')
        current_balance = cursor.fetchone()[0]
        
        if is_deposit:
            new_balance = current_balance + amount
        else:
            new_balance = current_balance - amount
        
        cursor.execute('''
            UPDATE cash_balance 
            SET amount_irr = %s, last_updated = %s 
            WHERE id = 1
        ''', (new_balance, datetime.now()))
    
    conn.commit()
    conn.close()
    
    return new_balance

def update_asset_current_price(asset_name, current_price):
    """
    Update the current price of an asset.
    
    Args:
        asset_name (str): Name of the asset
        current_price (float): Current price of the asset
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if USE_SQLITE:
        # SQLite version
        cursor.execute('''
            UPDATE assets 
            SET current_price = ?, last_updated = ? 
            WHERE asset_name = ?
        ''', (current_price, datetime.now(), asset_name))
    else:
        # PostgreSQL version
        cursor.execute('''
            UPDATE assets 
            SET current_price = %s, last_updated = %s 
            WHERE asset_name = %s
        ''', (current_price, datetime.now(), asset_name))
    
    conn.commit()
    conn.close()

def get_available_sale_transactions():
    """
    Get all sale transactions that can be linked to new purchases.
    These are sales that don't have all funds already used for purchases.
    
    Returns:
        list: List of dictionaries containing sale transaction details
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if USE_SQLITE:
            # SQLite version - Get sales that don't have all funds allocated
            cursor.execute('''
                SELECT s.id, s.trade_date, s.asset_name, s.asset_type, s.quantity, 
                       s.price, s.total_amount, s.profit_loss, s.notes, s.created_at
                FROM trades s
                WHERE s.trade_type = 'فروش' 
                ORDER BY s.trade_date DESC
            ''')
            sales = cursor.fetchall()
            
            # Get the column names
            columns = [column[0] for column in cursor.description]
            
            # Convert to list of dictionaries
            sales_list = []
            for sale in sales:
                sale_dict = dict(zip(columns, sale))
                
                # Get sum of related purchases for this sale
                cursor.execute('''
                    SELECT COALESCE(SUM(total_amount), 0) 
                    FROM trades 
                    WHERE related_trade_id = ? AND trade_type = 'خرید'
                ''', (sale_dict['id'],))
                allocated_amount = cursor.fetchone()[0] or 0
                
                # Calculate remaining amount
                sale_dict['available_amount'] = sale_dict['total_amount'] - allocated_amount
                
                # Only include if there's still money available
                if sale_dict['available_amount'] > 0:
                    sales_list.append(sale_dict)
                
        else:
            # PostgreSQL version
            cursor.execute('''
                SELECT s.id, s.trade_date, s.asset_name, s.asset_type, s.quantity, 
                       s.price, s.total_amount, s.profit_loss, s.notes, s.created_at
                FROM trades s
                WHERE s.trade_type = 'فروش'
                ORDER BY s.trade_date DESC
            ''')
            sales = cursor.fetchall()
            
            # Get the column names
            columns = [column[0] for column in cursor.description]
            
            # Convert to list of dictionaries
            sales_list = []
            for sale in sales:
                sale_dict = dict(zip(columns, sale))
                
                # Get sum of related purchases for this sale
                cursor.execute('''
                    SELECT COALESCE(SUM(total_amount), 0) 
                    FROM trades 
                    WHERE related_trade_id = %s AND trade_type = 'خرید'
                ''', (sale_dict['id'],))
                allocated_amount = cursor.fetchone()[0] or 0
                
                # Calculate remaining amount
                sale_dict['available_amount'] = sale_dict['total_amount'] - allocated_amount
                
                # Only include if there's still money available
                if sale_dict['available_amount'] > 0:
                    sales_list.append(sale_dict)
                
        conn.close()
        return sales_list
    except Exception as e:
        print(f"Error getting available sale transactions: {e}")
        return []

def delete_trade(trade_id):
    """
    Delete a trade and update related asset data.
    
    Args:
        trade_id (int): ID of the trade to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if USE_SQLITE:
            # SQLite version
            # Get trade information before deleting
            cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
            trade = cursor.fetchone()
            
            if not trade:
                conn.close()
                return False
                
            # Extract trade details
            asset_name = trade[2]
            asset_type = trade[3]
            
            # Delete the trade
            cursor.execute('DELETE FROM trades WHERE id = ?', (trade_id,))
        else:
            # PostgreSQL version
            # Get trade information before deleting
            cursor.execute('SELECT * FROM trades WHERE id = %s', (trade_id,))
            trade = cursor.fetchone()
            
            if not trade:
                conn.close()
                return False
                
            # Extract trade details
            asset_name = trade[2]
            asset_type = trade[3]
            
            # Delete the trade
            cursor.execute('DELETE FROM trades WHERE id = %s', (trade_id,))
            
        conn.commit()
        conn.close()
        
        # Recalculate asset data
        recalculate_asset_data(asset_name, asset_type)
        
        return True
    except Exception as e:
        print(f"Error deleting trade: {e}")
        return False

def recalculate_asset_data(asset_name, asset_type):
    """
    Recalculate asset data based on all related trades.
    
    Args:
        asset_name (str): Name of the asset
        asset_type (str): Type of the asset
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if USE_SQLITE:
            # SQLite version
            # Get all buy trades for the asset
            cursor.execute('''
                SELECT quantity, price, total_amount 
                FROM trades 
                WHERE asset_name = ? AND trade_type = 'خرید'
                ORDER BY trade_date
            ''', (asset_name,))
            buy_trades = cursor.fetchall()
            
            # Get all sell trades for the asset
            cursor.execute('''
                SELECT quantity 
                FROM trades 
                WHERE asset_name = ? AND trade_type = 'فروش'
                ORDER BY trade_date
            ''', (asset_name,))
            sell_trades = cursor.fetchall() or []
            
            # Calculate total bought and current quantity
            total_bought = sum(trade[0] for trade in buy_trades) if buy_trades else 0
            total_sold = sum(trade[0] for trade in sell_trades) if sell_trades else 0
            current_quantity = total_bought - total_sold
            
            # Calculate average buy price if there are buy trades
            if buy_trades:
                total_cost = sum(trade[0] * trade[1] for trade in buy_trades)
                avg_buy_price = total_cost / total_bought if total_bought > 0 else 0
            else:
                avg_buy_price = 0
                
            # Get current price
            cursor.execute('SELECT current_price FROM assets WHERE asset_name = ?', (asset_name,))
            result = cursor.fetchone()
            current_price = result[0] if result and result[0] is not None else 0
            
            # Update or insert asset data
            cursor.execute('''
                UPDATE assets 
                SET quantity = ?, avg_buy_price = ?, last_updated = ? 
                WHERE asset_name = ?
            ''', (current_quantity, avg_buy_price, datetime.now(), asset_name))
            
            if cursor.rowcount == 0:  # Asset doesn't exist
                cursor.execute('''
                    INSERT INTO assets (asset_name, asset_type, quantity, avg_buy_price, current_price, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (asset_name, asset_type, current_quantity, avg_buy_price, current_price, datetime.now()))
                
            # Update profit/loss values for sell trades
            for sell_trade in cursor.execute('''
                SELECT id, quantity, price FROM trades WHERE asset_name = ? AND trade_type = 'فروش'
            ''', (asset_name,)):
                sell_trade_id, sell_quantity, sell_price = sell_trade
                profit_loss = sell_quantity * (sell_price - avg_buy_price)
                cursor.execute('UPDATE trades SET profit_loss = ? WHERE id = ?', (profit_loss, sell_trade_id))
        
        else:
            # PostgreSQL version
            # Get all buy trades for the asset
            cursor.execute('''
                SELECT quantity, price, total_amount 
                FROM trades 
                WHERE asset_name = %s AND trade_type = 'خرید'
                ORDER BY trade_date
            ''', (asset_name,))
            buy_trades = cursor.fetchall() or []
            
            # Get all sell trades for the asset
            cursor.execute('''
                SELECT quantity 
                FROM trades 
                WHERE asset_name = %s AND trade_type = 'فروش'
                ORDER BY trade_date
            ''', (asset_name,))
            sell_trades = cursor.fetchall() or []
            
            # Calculate total bought and current quantity
            total_bought = sum(trade[0] for trade in buy_trades) if buy_trades else 0
            total_sold = sum(trade[0] for trade in sell_trades) if sell_trades else 0
            current_quantity = total_bought - total_sold
            
            # Calculate average buy price if there are buy trades
            if buy_trades:
                total_cost = sum(trade[0] * trade[1] for trade in buy_trades)
                avg_buy_price = total_cost / total_bought if total_bought > 0 else 0
            else:
                avg_buy_price = 0
                
            # Get current price
            cursor.execute('SELECT current_price FROM assets WHERE asset_name = %s', (asset_name,))
            result = cursor.fetchone()
            current_price = result[0] if result and result[0] is not None else 0
            
            # Update or insert asset data
            cursor.execute('''
                UPDATE assets 
                SET quantity = %s, avg_buy_price = %s, last_updated = %s 
                WHERE asset_name = %s
            ''', (current_quantity, avg_buy_price, datetime.now(), asset_name))
            
            if cursor.rowcount == 0:  # Asset doesn't exist
                cursor.execute('''
                    INSERT INTO assets (asset_name, asset_type, quantity, avg_buy_price, current_price, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (asset_name, asset_type, current_quantity, avg_buy_price, current_price, datetime.now()))
                
            # Update profit/loss values for sell trades
            cursor.execute('''
                SELECT id, quantity, price FROM trades WHERE asset_name = %s AND trade_type = 'فروش'
            ''', (asset_name,))
            
            for sell_trade in cursor.fetchall():
                sell_trade_id, sell_quantity, sell_price = sell_trade
                profit_loss = sell_quantity * (sell_price - avg_buy_price)
                cursor.execute('UPDATE trades SET profit_loss = %s WHERE id = %s', (profit_loss, sell_trade_id))
                
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error recalculating asset data: {e}")
        return False

def edit_trade(trade_id, trade_date, asset_name, asset_type, trade_type, quantity, price, notes, currency=None, is_profit_sale=None, trade_category=None):
    """
    Edit an existing trade.
    
    Args:
        trade_id (int): ID of the trade to edit
        trade_date (datetime): Date of the trade
        asset_name (str): Name of the asset
        asset_type (str): Type of the asset
        trade_type (str): Type of trade (خرید/فروش)
        quantity (float): Quantity traded
        price (float): Price of the trade
        notes (str): Trade notes
        currency (str, optional): The currency used for the trade (تومان/دلار)
        is_profit_sale (bool, optional): Whether this sale is from profit of previous trades
        trade_category (str, optional): The category of the trade
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if USE_SQLITE:
            # SQLite version
            # Get original trade data
            cursor.execute('SELECT asset_name, asset_type FROM trades WHERE id = ?', (trade_id,))
            original_trade = cursor.fetchone()
            
            if not original_trade:
                conn.close()
                return False
                
            original_asset_name = original_trade[0]
            original_asset_type = original_trade[1]
            
            # Calculate total amount
            total_amount = quantity * price
            
            # Calculate profit/loss for sell trade
            profit_loss = 0
            if trade_type == 'فروش':
                cursor.execute('SELECT avg_buy_price FROM assets WHERE asset_name = ?', (asset_name,))
                result = cursor.fetchone()
                if result and result[0]:
                    avg_buy_price = result[0]
                    profit_loss = quantity * (price - avg_buy_price)
            
            # Update the trade with optional parameters
            update_fields = [
                "trade_date = ?", "asset_name = ?", "asset_type = ?", "trade_type = ?",
                "quantity = ?", "price = ?", "total_amount = ?", "profit_loss = ?", "notes = ?"
            ]
            params = [trade_date, asset_name, asset_type, trade_type, quantity, price, 
                     total_amount, profit_loss, notes]
            
            # Add optional parameters if provided
            if currency is not None:
                update_fields.append("currency = ?")
                params.append(currency)
            
            if is_profit_sale is not None and trade_type == 'فروش':
                update_fields.append("is_profit_sale = ?")
                params.append(is_profit_sale)
                
            if trade_category is not None:
                update_fields.append("trade_category = ?")
                params.append(trade_category)
                
            # Add trade_id to params
            params.append(trade_id)
            
            # Build and execute the query
            query = f"UPDATE trades SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, params)
        else:
            # PostgreSQL version
            # Get original trade data
            cursor.execute('SELECT asset_name, asset_type FROM trades WHERE id = %s', (trade_id,))
            original_trade = cursor.fetchone()
            
            if not original_trade:
                conn.close()
                return False
                
            original_asset_name = original_trade[0]
            original_asset_type = original_trade[1]
            
            # Calculate total amount
            total_amount = quantity * price
            
            # Calculate profit/loss for sell trade
            profit_loss = 0
            if trade_type == 'فروش':
                cursor.execute('SELECT avg_buy_price FROM assets WHERE asset_name = %s', (asset_name,))
                result = cursor.fetchone()
                if result and result[0]:
                    avg_buy_price = result[0]
                    profit_loss = quantity * (price - avg_buy_price)
            
            # Update the trade with optional parameters
            update_fields = [
                "trade_date = %s", "asset_name = %s", "asset_type = %s", "trade_type = %s",
                "quantity = %s", "price = %s", "total_amount = %s", "profit_loss = %s", "notes = %s"
            ]
            params = [trade_date, asset_name, asset_type, trade_type, quantity, price, 
                     total_amount, profit_loss, notes]
            
            # Add optional parameters if provided
            if currency is not None:
                update_fields.append("currency = %s")
                params.append(currency)
            
            if is_profit_sale is not None and trade_type == 'فروش':
                update_fields.append("is_profit_sale = %s")
                params.append(is_profit_sale)
                
            if trade_category is not None:
                update_fields.append("trade_category = %s")
                params.append(trade_category)
                
            # Add trade_id to params
            params.append(trade_id)
            
            # Build and execute the query
            query = f"UPDATE trades SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, params)
        
        conn.commit()
        conn.close()
        
        # Recalculate asset data for both original and new asset if they're different
        recalculate_asset_data(asset_name, asset_type)
        if original_asset_name != asset_name:
            recalculate_asset_data(original_asset_name, original_asset_type)
        
        return True
    except Exception as e:
        print(f"Error editing trade: {e}")
        return False
