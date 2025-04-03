import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils import convert_to_jalali, format_number
from database import update_asset_current_price, get_connection, USE_SQLITE

def show_portfolio_page():
    """
    Display the portfolio management page with current assets, cash balance,
    and portfolio analysis.
    """
    st.header("پورتفولیو")

    # Get asset data and cash balance
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get active assets
        if USE_SQLITE:
            assets_df = pd.read_sql('''
                SELECT asset_name, asset_type, quantity, avg_buy_price, current_price 
                FROM assets 
                WHERE quantity > 0
            ''', conn)

            cursor.execute('SELECT amount_irr FROM cash_balance WHERE id = 1')
        else:
            import psycopg2.extras
            # Create a server-side cursor for PostgreSQL to avoid loading all data into memory
            assets_df = pd.read_sql('''
                SELECT asset_name, asset_type, quantity, avg_buy_price, current_price 
                FROM assets 
                WHERE quantity > 0
            ''', conn)

            cursor.execute('SELECT amount_irr FROM cash_balance WHERE id = 1')

        cash_data = cursor.fetchone()
        cash_balance_irr = cash_data[0] if cash_data else 0
    except Exception as e:
        st.error(f"خطا در بارگذاری اطلاعات: {e}")
        assets_df = pd.DataFrame(columns=['asset_name', 'asset_type', 'quantity', 'avg_buy_price', 'current_price'])
        cash_balance_irr = 0
    finally:
        conn.close()

    # Portfolio Visualization Section
    st.subheader("ترکیب دارایی‌ها")

    if not assets_df.empty:
        # Calculate asset values
        assets_df['total_value'] = assets_df['quantity'] * assets_df['current_price']
        assets_df['profit_loss'] = assets_df['quantity'] * (assets_df['current_price'] - assets_df['avg_buy_price'])
        assets_df['profit_loss_pct'] = ((assets_df['current_price'] - assets_df['avg_buy_price']) / 
                                       assets_df['avg_buy_price'] * 100)

        # Portfolio allocation chart (without cash)
        total_portfolio_value = assets_df['total_value'].sum()

        # Use asset_type for grouping in the pie chart
        portfolio_data = assets_df[['asset_name', 'asset_type', 'total_value']].copy()
        portfolio_data['percentage'] = portfolio_data['total_value'] / total_portfolio_value * 100

        # Create a more informative pie chart with distinct colors for each asset
        fig = px.pie(
            portfolio_data, 
            values='total_value', 
            names='asset_name', 
            color='asset_name',  # Color by asset name for distinct colors
            title=f'ترکیب دارایی‌ها - ارزش کل: {format_number(total_portfolio_value)} تومان',
            color_discrete_sequence=px.colors.qualitative.Set3  # Use a colorful palette
        )

        fig.update_layout(
            font=dict(family="Nazanin, Vazirmatn, B Nazanin, tahoma, sans-serif", size=14),
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("هیچ دارایی در پورتفولیو ثبت نشده است.")

    # Asset List
    st.subheader("لیست دارایی‌ها")

    # Get asset data 
    conn = get_connection()
    try:
        assets_df = pd.read_sql('SELECT * FROM assets ORDER BY asset_type, asset_name', conn)
    except Exception as e:
        st.error(f"خطا در بارگذاری اطلاعات دارایی‌ها: {e}")
        assets_df = pd.DataFrame(columns=['id', 'asset_name', 'asset_type', 'quantity', 'avg_buy_price', 'current_price', 'last_updated'])
    finally:
        conn.close()

    if not assets_df.empty:
        # Add calculated columns for display
        assets_df['total_value'] = assets_df['quantity'] * assets_df['current_price']
        assets_df['profit_loss'] = assets_df['quantity'] * (assets_df['current_price'] - assets_df['avg_buy_price'])
        assets_df['profit_loss_pct'] = ((assets_df['current_price'] - assets_df['avg_buy_price']) / 
                                       assets_df['avg_buy_price'] * 100).round(2)

        # Add asset_type to display dataframe for better organization
        display_df = assets_df[['asset_name', 'asset_type', 'quantity', 'avg_buy_price', 'current_price', 
                             'total_value', 'profit_loss', 'profit_loss_pct']].copy()

        display_df.columns = [
            'نام دارایی', 'نوع دارایی', 'تعداد', 'قیمت خرید (تومان)', 'قیمت فعلی (تومان)', 
            'ارزش کل (تومان)', 'سود/زیان (تومان)', 'سود/زیان (%)'
        ]

        # Apply formatting
        for col in ['قیمت خرید (تومان)', 'قیمت فعلی (تومان)', 'ارزش کل (تومان)', 'سود/زیان (تومان)']:
            display_df[col] = display_df[col].apply(format_number)

        # Get all sell trades data
        conn = get_connection()
        try:
            query = '''
                SELECT asset_name, asset_type, SUM(quantity) as total_quantity, 
                SUM(total_amount) as total_sales
                FROM trades 
                WHERE trade_type = 'فروش'
                GROUP BY asset_name, asset_type
                ORDER BY asset_type, asset_name
            '''

            sell_trades_df = pd.read_sql(query, conn)
        except Exception as e:
            st.error(f"خطا در بارگذاری اطلاعات فروش: {e}")
            sell_trades_df = pd.DataFrame(columns=['asset_name', 'asset_type', 'total_quantity', 'total_sales'])
        finally:
            conn.close()

        # Create the final display dataframe
        final_display_df = pd.DataFrame(columns=display_df.columns)

        # Group assets by asset_name for display
        asset_names = display_df['نام دارایی'].unique()

        # Add each asset and its sale total (if any)
        for asset_name in asset_names:
            # Get asset data
            asset_data = display_df[display_df['نام دارایی'] == asset_name]
            asset_type = asset_data['نوع دارایی'].iloc[0]

            # Add asset row to final dataframe
            final_display_df = pd.concat([final_display_df, asset_data])

            # Check if this asset has sell transactions
            if not sell_trades_df.empty:
                sell_data = sell_trades_df[(sell_trades_df['asset_name'] == asset_name) & 
                                         (sell_trades_df['asset_type'] == asset_type)]

                if not sell_data.empty:
                    # Create total row with only quantity and total value
                    sell_row = sell_data.iloc[0]
                    total_row = pd.DataFrame([{
                        'نام دارایی': f"جمع کل فروش: {asset_name}",
                        'نوع دارایی': asset_type,
                        'تعداد': str(format_number(sell_row['total_quantity'])),
                        'قیمت خرید (تومان)': '',
                        'قیمت فعلی (تومان)': '',
                        'ارزش کل (تومان)': format_number(sell_row['total_sales']),
                        'سود/زیان (تومان)': '',
                        'سود/زیان (%)': ''
                    }])

                    # Make sure 'تعداد' column is properly converted to string before concatenation to avoid type conversion issues
                    if 'تعداد' in total_row.columns:
                        total_row['تعداد'] = total_row['تعداد'].astype(str)

                    # Add total sales row to final dataframe
                    final_display_df = pd.concat([final_display_df, total_row], sort=False)

                    # Ensure all numeric columns that might be displayed as string are properly handled
                    if 'تعداد' in final_display_df.columns:
                        final_display_df['تعداد'] = final_display_df['تعداد'].astype(str)

        # Display the consolidated dataframe
        st.dataframe(final_display_df.reset_index(drop=True), use_container_width=True)

        # Update current price controls
        st.subheader("بروزرسانی قیمت دارایی‌ها")

        # Group assets by type for update controls
        asset_types = assets_df['asset_type'].unique()

        for asset_type in asset_types:
            with st.expander(f"بروزرسانی قیمت های {asset_type}", expanded=False):
                type_assets = assets_df[assets_df['asset_type'] == asset_type].copy()

                for idx, asset in type_assets.iterrows():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        new_price = st.number_input(
                            f"قیمت جدید برای {asset['asset_name']} (تومان)",
                            min_value=0.0,
                            value=float(asset['current_price']),
                            key=f"price_{asset['id']}"
                        )
                    with col2:
                        if st.button("بروزرسانی قیمت", key=f"update_{asset['id']}"):
                            update_asset_current_price(asset['asset_name'], new_price)
                            st.success(f"قیمت {asset['asset_name']} بروزرسانی شد.")
                            st.rerun()
    else:
        st.info("هیچ دارایی در پورتفولیو ثبت نشده است.")