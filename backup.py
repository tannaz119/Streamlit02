import os
import shutil
import datetime
import streamlit as st
from database import get_connection, USE_SQLITE

def create_backup():
    """
    Create a backup of the database.
    
    Returns:
        str: Path to the backup file if successful, None otherwise
    """
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if USE_SQLITE:
            # SQLite backup
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            original_db = "portfolio.db"
            backup_file = f"{backup_dir}/portfolio_{timestamp}.db"
            
            # Create a copy of the database file
            shutil.copy2(original_db, backup_file)
            
            return backup_file
        else:
            # PostgreSQL backup using pg_dump
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                return None
                
            # Parse the database URL to get connection details
            import re
            match = re.match(r"postgres://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)", database_url)
            if match:
                username, password, host, port, dbname = match.groups()
                
                # Set environment variables for pg_dump
                env = os.environ.copy()
                env["PGPASSWORD"] = password
                
                backup_file = f"{backup_dir}/portfolio_{timestamp}.sql"
                
                # Execute pg_dump
                import subprocess
                cmd = [
                    "pg_dump",
                    "-h", host,
                    "-p", port,
                    "-U", username,
                    "-F", "c",  # Custom format
                    "-b",  # Include large objects
                    "-v",  # Verbose
                    "-f", backup_file,
                    dbname
                ]
                
                process = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                if process.returncode == 0:
                    return backup_file
                else:
                    print(f"Error creating PostgreSQL backup: {process.stderr}")
                    return None
            else:
                print("Could not parse DATABASE_URL")
                return None
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

def list_backups():
    """
    List all available backups.
    
    Returns:
        list: List of backup files
    """
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        return []
        
    if USE_SQLITE:
        # List SQLite backup files
        return [f for f in os.listdir(backup_dir) if f.endswith(".db")]
    else:
        # List PostgreSQL backup files
        return [f for f in os.listdir(backup_dir) if f.endswith(".sql")]

def restore_backup(backup_file):
    """
    Restore a database from a backup file.
    
    Args:
        backup_file (str): Path to the backup file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if USE_SQLITE:
            # SQLite restore
            backup_path = os.path.join("backups", backup_file)
            original_db = "portfolio.db"
            
            # First close any open connections
            # This is simplified; in a real app, you might need to handle
            # open connections more carefully
            import sqlite3
            try:
                conn = sqlite3.connect(original_db)
                conn.close()
            except:
                pass
                
            # Restore by copying the backup over the original
            shutil.copy2(backup_path, original_db)
            
            return True
        else:
            # PostgreSQL restore using pg_restore
            backup_path = os.path.join("backups", backup_file)
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                return False
                
            # Parse the database URL to get connection details
            import re
            match = re.match(r"postgres://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)", database_url)
            if match:
                username, password, host, port, dbname = match.groups()
                
                # Set environment variables for pg_restore
                env = os.environ.copy()
                env["PGPASSWORD"] = password
                
                # Execute pg_restore
                import subprocess
                cmd = [
                    "pg_restore",
                    "-h", host,
                    "-p", port,
                    "-U", username,
                    "-d", dbname,
                    "-c",  # Clean (drop) database objects before recreating
                    "-v",  # Verbose
                    backup_path
                ]
                
                process = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                if process.returncode == 0:
                    return True
                else:
                    print(f"Error restoring PostgreSQL backup: {process.stderr}")
                    return False
            else:
                print("Could not parse DATABASE_URL")
                return False
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return False

def show_backup_page():
    """
    Display the backup management page.
    """
    st.header("مدیریت پشتیبان‌گیری")
    
    st.subheader("ایجاد نسخه پشتیبان")
    if st.button("ایجاد نسخه پشتیبان جدید"):
        with st.spinner("در حال ایجاد نسخه پشتیبان..."):
            backup_file = create_backup()
            if backup_file:
                st.success(f"نسخه پشتیبان با موفقیت ایجاد شد: {backup_file}")
            else:
                st.error("خطا در ایجاد نسخه پشتیبان")
    
    st.subheader("بازیابی نسخه پشتیبان")
    backups = list_backups()
    
    if not backups:
        st.info("هیچ نسخه پشتیبانی موجود نیست")
    else:
        selected_backup = st.selectbox(
            "انتخاب نسخه پشتیبان برای بازیابی",
            backups,
            format_func=lambda x: x.replace(".db", "").replace(".sql", "").replace("portfolio_", "")
        )
        
        if st.button("بازیابی نسخه پشتیبان"):
            confirm = st.checkbox("من تأیید می‌کنم که این عملیات اطلاعات فعلی را با نسخه پشتیبان جایگزین می‌کند")
            
            if confirm:
                with st.spinner("در حال بازیابی نسخه پشتیبان..."):
                    if restore_backup(selected_backup):
                        st.success("نسخه پشتیبان با موفقیت بازیابی شد")
                        st.rerun()
                    else:
                        st.error("خطا در بازیابی نسخه پشتیبان")
            else:
                st.warning("لطفاً تأیید کنید که می‌خواهید نسخه پشتیبان را بازیابی کنید")
    
    st.subheader("لیست نسخه‌های پشتیبان")
    if not backups:
        st.info("هیچ نسخه پشتیبانی موجود نیست")
    else:
        for backup in backups:
            col1, col2 = st.columns([3, 1])
            with col1:
                date_str = backup.replace(".db", "").replace(".sql", "").replace("portfolio_", "")
                try:
                    date_obj = datetime.datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                    formatted_date = date_obj.strftime("%Y/%m/%d %H:%M:%S")
                    st.text(f"تاریخ: {formatted_date}")
                except:
                    st.text(f"فایل: {backup}")
            
            with col2:
                if st.button("حذف", key=f"delete_{backup}"):
                    try:
                        os.remove(os.path.join("backups", backup))
                        st.success("نسخه پشتیبان با موفقیت حذف شد")
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطا در حذف نسخه پشتیبان: {e}")