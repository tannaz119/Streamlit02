import streamlit as st
import pandas as pd
import jdatetime
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from database import initialize_database, update_database_schema, get_connection
from portfolio import show_portfolio_page
from trades import show_trades_page
from backup import show_backup_page
from utils import convert_to_jalali, convert_to_gregorian, format_number

# Set page config
st.set_page_config(
    page_title="سیستم مدیریت پورتفولیو و ژورنال معاملاتی",
    page_icon="📊",
    layout="wide",
)

# Initialize database
initialize_database()
# Update database schema (add new columns if needed)
update_database_schema()

# Set application title
st.title("سیستم مدیریت پورتفولیو و ژورنال معاملاتی")

# Create tabs for different sections of the application
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "پورتفولیو", 
    "ژورنال معاملات", 
    "استراتژی", 
    "گزارشات",
    "پشتیبان‌گیری"
])

# Portfolio Tab
with tab1:
    show_portfolio_page()

# Trading Journal Tab
with tab2:
    show_trades_page()

# Strategy Tab
with tab3:
    st.header("استراتژی مدیریت پورتفولیو")
    
    # Strategy Input
    with st.expander("تعریف استراتژی جدید"):
        strategy_name = st.text_input("نام استراتژی", key="strategy_name")
        strategy_desc = st.text_area("توضیحات استراتژی", key="strategy_desc")
        asset_allocation = st.text_area("تخصیص دارایی (مثال: سهام ۵۰٪ - ارز دیجیتال ۳۰٪ - طلا ۲۰٪)", key="asset_allocation")
        risk_level = st.select_slider("سطح ریسک", options=["بسیار کم", "کم", "متوسط", "زیاد", "بسیار زیاد"], key="risk_level")
        
        if st.button("ذخیره استراتژی", key="save_strategy"):
            conn = get_connection()
            cursor = conn.cursor()
            
            # Check if using PostgreSQL or SQLite
            from database import USE_SQLITE
            if USE_SQLITE:
                cursor.execute('''
                    INSERT INTO strategies (name, description, asset_allocation, risk_level, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (strategy_name, strategy_desc, asset_allocation, risk_level, datetime.now()))
            else:
                cursor.execute('''
                    INSERT INTO strategies (name, description, asset_allocation, risk_level, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (strategy_name, strategy_desc, asset_allocation, risk_level, datetime.now()))
            
            conn.commit()
            conn.close()
            st.success("استراتژی با موفقیت ذخیره شد.")
            st.rerun()
    
    # Display defined strategies
    conn = get_connection()
    strategies_df = pd.read_sql('SELECT * FROM strategies ORDER BY created_at DESC', conn)
    conn.close()
    
    if not strategies_df.empty:
        for _, strategy in strategies_df.iterrows():
            with st.expander(f"استراتژی: {strategy['name']}"):
                st.write(f"**توضیحات:** {strategy['description']}")
                st.write(f"**تخصیص دارایی:** {strategy['asset_allocation']}")
                st.write(f"**سطح ریسک:** {strategy['risk_level']}")
                created_at = datetime.strptime(strategy['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                jalali_date = convert_to_jalali(created_at)
                st.write(f"**تاریخ ایجاد:** {jalali_date.strftime('%Y/%m/%d')}")
    else:
        st.info("هنوز استراتژی تعریف نشده است.")

# Reports Tab
with tab4:
    st.header("گزارشات و تحلیل‌ها")
    
    # Get data for reports
    conn = get_connection()
    trades_df = pd.read_sql('SELECT * FROM trades', conn)
    assets_df = pd.read_sql('SELECT * FROM assets', conn)
    conn.close()
    
    if not trades_df.empty:
        # Convert dates for display
        trades_df['trade_date'] = pd.to_datetime(trades_df['trade_date'])
        trades_df['jalali_date'] = trades_df['trade_date'].apply(lambda x: convert_to_jalali(x).strftime('%Y/%m/%d'))
        
        # Monthly profit/loss report
        st.subheader("گزارش سود/زیان ماهانه")
        
        # Extract year and month for grouping
        trades_df['year_month'] = trades_df['trade_date'].dt.strftime('%Y-%m')
        
        # Calculate realized profit/loss by month
        monthly_pnl = trades_df[trades_df['trade_type'] == 'فروش'].groupby('year_month').agg({
            'profit_loss': 'sum'
        }).reset_index()
        
        if not monthly_pnl.empty:
            fig = px.bar(monthly_pnl, x='year_month', y='profit_loss', 
                        labels={'year_month': 'ماه', 'profit_loss': 'سود/زیان (تومان)'},
                        title='سود/زیان ماهانه')
            fig.update_layout(xaxis_title="ماه", yaxis_title="سود/زیان (تومان)")
            st.plotly_chart(fig)
        else:
            st.info("داده‌ای برای نمایش گزارش ماهانه وجود ندارد.")
        
        # Asset performance
        st.subheader("عملکرد دارایی‌ها")
        
        if not assets_df.empty:
            # Calculate performance by asset
            asset_performance = assets_df.copy()
            asset_performance['performance_pct'] = (asset_performance['current_price'] - 
                                                asset_performance['avg_buy_price']) / asset_performance['avg_buy_price'] * 100
            
            fig = px.bar(asset_performance, x='asset_name', y='performance_pct',
                        color='performance_pct',
                        color_continuous_scale=['red', 'green'],
                        labels={'asset_name': 'دارایی', 'performance_pct': 'بازدهی (%)'},
                        title='بازدهی دارایی‌ها')
            fig.update_layout(xaxis_title="دارایی", yaxis_title="بازدهی (%)")
            st.plotly_chart(fig)
            
            # Trade count by asset
            trade_counts = trades_df.groupby('asset_name').size().reset_index(name='count')
            fig = px.pie(trade_counts, values='count', names='asset_name', title='تعداد معاملات بر اساس دارایی')
            st.plotly_chart(fig)
            
            # Related trades report
            st.subheader("گزارش سرمایه‌گذاری مجدد")
            related_trades = trades_df[(pd.notna(trades_df['related_trade_id'])) & (trades_df['trade_type'] == 'خرید')]
            
            if not related_trades.empty:
                # Create a dataframe for relationship visualization
                relationship_data = []
                for _, row in related_trades.iterrows():
                    related_sale = trades_df[trades_df['id'] == row['related_trade_id']]
                    if not related_sale.empty:
                        sale_row = related_sale.iloc[0]
                        relationship_data.append({
                            'buy_date': row['jalali_date'],
                            'buy_asset': row['asset_name'],
                            'buy_amount': row['total_amount'],
                            'sale_date': sale_row['jalali_date'],
                            'sale_asset': sale_row['asset_name'],
                            'sale_amount': sale_row['total_amount'],
                            'percentage': (row['total_amount'] / sale_row['total_amount'] * 100)
                        })
                
                if relationship_data:
                    relationship_df = pd.DataFrame(relationship_data)
                    
                    # Format for display
                    relationship_df['buy_amount'] = relationship_df['buy_amount'].apply(format_number)
                    relationship_df['sale_amount'] = relationship_df['sale_amount'].apply(format_number)
                    relationship_df['percentage'] = relationship_df['percentage'].apply(lambda x: f"{x:.1f}%")
                    
                    # Rename columns
                    relationship_df.columns = [
                        'تاریخ خرید', 'دارایی خریداری شده', 'مبلغ خرید (تومان)',
                        'تاریخ فروش', 'دارایی فروخته شده', 'مبلغ فروش (تومان)',
                        'درصد استفاده شده'
                    ]
                    
                    st.dataframe(relationship_df, use_container_width=True)
                    
                    # Trade category distribution
                    if 'trade_category' in trades_df.columns:
                        buy_categories = trades_df[trades_df['trade_type'] == 'خرید']['trade_category'].value_counts().reset_index()
                        buy_categories.columns = ['دسته‌بندی', 'تعداد']
                        
                        fig = px.pie(buy_categories, values='تعداد', names='دسته‌بندی', title='دسته‌بندی خریدها')
                        st.plotly_chart(fig)
                        
                        sell_categories = trades_df[trades_df['trade_type'] == 'فروش']['trade_category'].value_counts().reset_index()
                        sell_categories.columns = ['دسته‌بندی', 'تعداد']
                        
                        fig = px.pie(sell_categories, values='تعداد', names='دسته‌بندی', title='دسته‌بندی فروش‌ها')
                        st.plotly_chart(fig)
            else:
                st.info("هنوز معامله‌ای با استفاده از منابع حاصل از فروش انجام نشده است.")
        else:
            st.info("داده‌ای برای نمایش عملکرد دارایی‌ها وجود ندارد.")
    else:
        st.info("برای نمایش گزارشات، ابتدا معاملات خود را ثبت کنید.")

# Backup Tab
with tab5:
    show_backup_page()