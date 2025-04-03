import streamlit as st
import pandas as pd
from datetime import datetime
import jdatetime
import sqlite3

from database import (
    update_asset_after_trade, update_cash_balance, get_connection, 
    USE_SQLITE, get_available_sale_transactions, recalculate_asset_data, delete_trade
)
from utils import convert_to_jalali, convert_to_gregorian, format_number

def show_trades_page():
    """
    Display the trading journal page with trade entry form and history.
    """
    st.header("ژورنال معاملات")

    # Main page layout - two sections side by side for entry form and trade history
    entry_col, history_col = st.columns([1, 2])

    # Trade entry form section
    with entry_col:
        st.subheader("ثبت معامله جدید")

        with st.form("trade_form"):
            # Asset information
            asset_type = st.selectbox(
                "نوع دارایی",
                ["سهام", "ارز دیجیتال", "طلا و سکه", "ارز", "کالا", "سایر"],
                key="asset_type"
            )

            # Get existing assets for the selected type
            conn = get_connection()
            cursor = conn.cursor()

            # Check if using PostgreSQL or SQLite
            if USE_SQLITE:
                cursor.execute('SELECT DISTINCT asset_name FROM assets WHERE asset_type = ?', (asset_type,))
            else:
                cursor.execute('SELECT DISTINCT asset_name FROM assets WHERE asset_type = %s', (asset_type,))

            existing_assets = [row[0] for row in cursor.fetchall()]
            conn.close()

            # Always allow entering custom asset name
            if existing_assets:
                asset_name = st.selectbox("انتخاب از دارایی‌های موجود", 
                                       ["-- وارد کردن دارایی جدید --"] + existing_assets, 
                                       key="asset_selection")

                if asset_name == "-- وارد کردن دارایی جدید --":
                    asset_name = st.text_input("نام دارایی جدید", key="new_asset")
            else:
                asset_name = st.text_input("نام دارایی", key="new_asset")

            # Trade details
            trade_type = st.radio("نوع معامله", ["خرید", "فروش"], horizontal=True, key="trade_type")

            # Date picker for Jalali (Shamsi) date
            today_jalali = jdatetime.datetime.now()

            # Convert to string for display in date_input
            today_str = f"{today_jalali.year}-{today_jalali.month:02d}-{today_jalali.day:02d}"

            # Single line date picker
            jalali_date_str = st.text_input("تاریخ معامله (سال-ماه-روز)", value=today_str, 
                                          placeholder="مثال: 1402-01-15", key="jalali_date")

            try:
                # Parse date from text input
                date_parts = jalali_date_str.split('-')
                if len(date_parts) == 3:
                    selected_year = int(date_parts[0])
                    selected_month = int(date_parts[1])
                    selected_day = int(date_parts[2])

                    selected_jalali_date = jdatetime.datetime(selected_year, selected_month, selected_day)
                    trade_date = selected_jalali_date.togregorian()
                else:
                    raise ValueError("فرمت تاریخ صحیح نیست")
            except ValueError:
                st.error("تاریخ وارد شده معتبر نیست. لطفاً با فرمت سال-ماه-روز وارد کنید.")
                trade_date = datetime.now()

            # Trade amount details
            quantity = st.number_input("تعداد/مقدار", min_value=0.0, key="quantity")

            col1, col2 = st.columns(2)
            # واحد ارزی بالای قیمت واحد
            currency = st.selectbox("واحد ارزی", ["تومان", "دلار"], key="currency")
            price = st.number_input("قیمت واحد", min_value=0.0, key="price")

            # Calculate total
            total_amount = quantity * price
            st.write(f"مبلغ کل: {format_number(total_amount)} {currency}")

            # Trade category and related sale for buys
            related_trade_id = None
            trade_category = None

            if trade_type == "خرید":
                # Get available sales with remaining funds
                available_sales = get_available_sale_transactions()

                if available_sales:
                    st.write("### استفاده از منابع حاصل از فروش‌های قبلی")
                    st.write("شما می‌توانید این خرید را به یک یا چند فروش قبلی مرتبط کنید:")

                        # Create a list of choices for the multiselect
                    sale_options = []
                    for sale in available_sales:
                        sale_date = convert_to_jalali(pd.to_datetime(sale['trade_date'])).strftime('%Y/%m/%d')
                        sale_description = f"شناسه {sale['id']}: {sale['asset_name']} - {format_number(sale['available_amount'])} تومان ({sale_date})"
                        sale_options.append((sale['id'], sale_description))

                        # Show multiselect for sale IDs with clear labeling
                    selected_sales = st.multiselect(
                        "انتخاب منبع تأمین وجه بر اساس شناسه (می‌توانید چند مورد انتخاب کنید)",
                        options=[s[0] for s in sale_options],
                        format_func=lambda x: next((s[1] for s in sale_options if s[0] == x), str(x))
                    )

                    # Use the first selected ID as primary related_trade_id
                    related_trade_id = selected_sales[0] if selected_sales else None

                    # Show all selected IDs clearly
                    if len(selected_sales) > 1:
                        st.info(f"شناسه‌های انتخاب شده برای تأمین وجه: {', '.join(map(str, selected_sales))}")

                    if related_trade_id:
                        # Get the selected sale details
                        selected_sale_details = next((s for s in available_sales if s['id'] == related_trade_id), None)

                        if selected_sale_details:
                            # Check if the current purchase amount exceeds the available amount
                            if total_amount > selected_sale_details['available_amount']:
                                st.warning(f"مبلغ خرید ({format_number(total_amount)} تومان) بیشتر از مبلغ قابل استفاده از فروش انتخاب شده ({format_number(selected_sale_details['available_amount'])} تومان) است. مابقی از موجودی نقدی کسر خواهد شد.")

                            # Set the trade category
                            trade_category = "سرمایه‌گذاری مجدد"

                # Allow manual category entry for buys
                categories = [
                    "سرمایه‌گذاری جدید",
                    "سرمایه‌گذاری مجدد",
                    "افزایش سبد",
                    "متنوع‌سازی",
                    "سایر"
                ]

                # Don't show category selection if we already selected a related sale
                if not trade_category:
                    trade_category = st.selectbox(
                        "دسته‌بندی معامله",
                        options=categories,
                        index=0
                    )

            # For sell transactions
            is_profit_sale = False
            if trade_type == "فروش":
                # Category options for sells
                categories = [
                    "برداشت سود",
                    "کاهش ضرر",
                    "تغییر استراتژی",
                    "نیاز به نقدینگی",
                    "سایر"
                ]

                trade_category = st.selectbox(
                    "دسته‌بندی معامله",
                    options=categories,
                    index=0
                )

                # Option to mark if the sale was from profit of previous trades
                is_profit_sale = st.checkbox(
                    "این فروش از محل سود معاملات قبلی انجام شده است",
                    value=False,
                    key="is_profit_sale_checkbox"
                )

            # Notes
            notes = st.text_area("توضیحات", key="notes")

            # Initialize profit_loss (will be calculated in backend)
            profit_loss = 0

            # Submit button
            submitted = st.form_submit_button("ثبت معامله")

            if submitted:
                if not asset_name:
                    st.error("لطفاً نام دارایی را وارد کنید.")
                elif quantity <= 0:
                    st.error("مقدار باید بزرگتر از صفر باشد.")
                elif price <= 0:
                    st.error("قیمت باید بزرگتر از صفر باشد.")
                else:
                    # Insert the trade into database
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Check if we have enough assets to sell
                    if trade_type == "فروش":
                        if USE_SQLITE:
                            cursor.execute('SELECT quantity FROM assets WHERE asset_name = ?', (asset_name,))
                        else:
                            cursor.execute('SELECT quantity FROM assets WHERE asset_name = %s', (asset_name,))

                        result = cursor.fetchone()

                        if not result or result[0] < quantity:
                            st.error(f"تعداد کافی از دارایی {asset_name} برای فروش وجود ندارد.")
                            conn.close()
                        else:
                            # Set profit_loss to 0 for sell trades as per requirement
                            profit_loss = 0

                            # Insert trade record
                            if USE_SQLITE:
                                cursor.execute('''
                                    INSERT INTO trades (trade_date, asset_name, asset_type, trade_type, 
                                                      quantity, price, total_amount, profit_loss, 
                                                      related_trade_id, trade_category, is_profit_sale, currency, notes)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (trade_date, asset_name, asset_type, trade_type, quantity, 
                                     price, total_amount, profit_loss, related_trade_id, trade_category, 
                                     is_profit_sale, currency, notes))
                            else:
                                cursor.execute('''
                                    INSERT INTO trades (trade_date, asset_name, asset_type, trade_type, 
                                                      quantity, price, total_amount, profit_loss, 
                                                      related_trade_id, trade_category, is_profit_sale, currency, notes)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ''', (trade_date, asset_name, asset_type, trade_type, quantity, 
                                     price, total_amount, profit_loss, related_trade_id, trade_category, 
                                     is_profit_sale, currency, notes))

                            # Close database connection before other operations
                            conn.commit()
                            conn.close()

                            # Update asset data
                            if update_asset_after_trade(asset_name, asset_type, quantity, price, trade_type):
                                # Update cash balance
                                update_cash_balance(total_amount, trade_type == "فروش")
                                st.success(f"معامله با موفقیت ثبت شد. مبلغ کل: {format_number(total_amount)} تومان")
                                st.rerun()
                            else:
                                st.error("خطا در ثبت معامله. لطفا دوباره تلاش کنید.")
                    else:  # Buy trade
                        # Insert trade record
                        if USE_SQLITE:
                            cursor.execute('''
                                INSERT INTO trades (trade_date, asset_name, asset_type, trade_type, 
                                                  quantity, price, total_amount, profit_loss,
                                                  related_trade_id, trade_category, is_profit_sale, currency, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (trade_date, asset_name, asset_type, trade_type, quantity, 
                                 price, total_amount, 0, related_trade_id, trade_category, False, currency, notes))
                        else:
                            cursor.execute('''
                                INSERT INTO trades (trade_date, asset_name, asset_type, trade_type, 
                                                  quantity, price, total_amount, profit_loss,
                                                  related_trade_id, trade_category, is_profit_sale, currency, notes)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''', (trade_date, asset_name, asset_type, trade_type, quantity, 
                                 price, total_amount, 0, related_trade_id, trade_category, False, currency, notes))

                        # Close database connection before other operations
                        conn.commit()
                        conn.close()

                        # Update asset data
                        if update_asset_after_trade(asset_name, asset_type, quantity, price, trade_type):
                            # Update cash balance (subtract for buy)
                            update_cash_balance(total_amount, False)
                            st.success(f"معامله با موفقیت ثبت شد. مبلغ کل: {format_number(total_amount)} تومان")
                            st.rerun()
                        else:
                            st.error("خطا در ثبت معامله. لطفا دوباره تلاش کنید.")

    with history_col:
        st.subheader("تاریخچه معاملات")

        # گزینه‌های فیلتر
        filter_col1, filter_col2 = st.columns(2)

        # Get trades data
        conn = get_connection()
        trades_df = pd.read_sql('''
            SELECT * FROM trades 
            ORDER BY trade_date DESC, id DESC
        ''', conn)

        # فیلتر بر اساس نوع دارایی
        with filter_col1:
            asset_types = ["همه"] + list(trades_df["asset_type"].unique()) if not trades_df.empty else ["همه"]
            selected_asset_type = st.selectbox("فیلتر بر اساس نوع دارایی", asset_types)

        # فیلتر بر اساس نوع معامله
        with filter_col2:
            trade_types = ["همه", "خرید", "فروش"]
            selected_trade_type = st.selectbox("فیلتر بر اساس نوع معامله", trade_types)

        # اعمال فیلترها
        filtered_data = trades_df.copy()
        if not trades_df.empty:
            if selected_asset_type != "همه":
                filtered_data = filtered_data[filtered_data["asset_type"] == selected_asset_type]
            if selected_trade_type != "همه":
                filtered_data = filtered_data[filtered_data["trade_type"] == selected_trade_type]

        trades_df = filtered_data
        conn.close()

        if not trades_df.empty:
            # Convert dates for display
            trades_df['trade_date'] = pd.to_datetime(trades_df['trade_date'])
            trades_df['jalali_date'] = trades_df['trade_date'].apply(lambda x: convert_to_jalali(x).strftime('%Y/%m/%d'))

            # Add related trades information
            trades_df['related_trade_info'] = None
            for idx, row in trades_df.iterrows():
                if pd.notna(row['related_trade_id']) and row['trade_type'] == 'خرید':
                    # Find the related sale
                    related_sale = trades_df[trades_df['id'] == row['related_trade_id']]
                    if not related_sale.empty:
                        related_sale_row = related_sale.iloc[0]
                        trades_df.at[idx, 'related_trade_info'] = f"خرید از فروش {related_sale_row['asset_name']} در تاریخ {related_sale_row['jalali_date']}"

            # Format currency for display
            trades_df['formatted_price'] = trades_df.apply(
                lambda row: f"{format_number(row['price'])} {row['currency'] if pd.notna(row['currency']) else 'تومان'}", 
                axis=1
            )

            trades_df['formatted_total'] = trades_df.apply(
                lambda row: f"{format_number(row['total_amount'])} {row['currency'] if pd.notna(row['currency']) else 'تومان'}", 
                axis=1
            )

            # Format profit/loss for display (نمایش علامت - برای معاملات فروش)
            trades_df['formatted_profit_loss'] = trades_df.apply(
                lambda row: "-" if row['trade_type'] == 'فروش' else f"{format_number(row['profit_loss'])} تومان", 
                axis=1
            )

            # Convert boolean to text for is_profit_sale
            trades_df['profit_sale_text'] = trades_df.apply(
                lambda row: "بله" if pd.notna(row['is_profit_sale']) and row['is_profit_sale'] else "خیر" if row['trade_type'] == 'فروش' else "", 
                axis=1
            )

            # Create a display dataframe with selected columns for showing in the UI
            display_columns = [
                'id', 'jalali_date', 'asset_name', 'trade_type', 
                'quantity', 'formatted_price', 'formatted_total', 
                'formatted_profit_loss', 'trade_category', 'profit_sale_text', 
                'related_trade_info', 'notes'
            ]

            display_df = trades_df[display_columns].copy()

            # Rename columns for display
            display_df.columns = [
                'شناسه', 'تاریخ', 'نام دارایی', 'نوع معامله',
                'تعداد', 'قیمت واحد', 'مبلغ کل',
                'سود/زیان', 'دسته‌بندی', 'فروش از محل سود',
                'مرتبط با معامله', 'توضیحات'
            ]

            # افزودن قابلیت انتخاب ستون‌های مورد نظر برای نمایش
            available_columns = [
                'شناسه', 'تاریخ', 'نام دارایی', 'نوع معامله',
                'تعداد', 'قیمت واحد', 'مبلغ کل',
                'سود/زیان', 'دسته‌بندی', 'فروش از محل سود',
                'مرتبط با معامله', 'توضیحات'
            ]

            # درصورتی که selected_columns در session_state وجود نداشته باشد، آن را با مقدار پیش‌فرض مقداردهی کن
            if 'selected_columns' not in st.session_state:
                st.session_state.selected_columns = available_columns

            # کنترل کوچک و ساده برای نمایش ستون‌ها
            with st.expander("⚙️ تنظیمات نمایش ستون‌ها", expanded=False):
                st.markdown("""
                    <div style="font-family: 'Nazanin', 'Vazirmatn', 'B Nazanin', tahoma, sans-serif; font-size: 14px; padding-bottom: 10px;">
                    ستون‌های مورد نظر خود را برای نمایش انتخاب کنید:
                    </div>
                """, unsafe_allow_html=True)

                # مقادیر موقت برای نگهداری وضعیت انتخاب‌ها
                temp_selected = []

                # نمایش چکباکس‌ها در سه ستون برای کوچکتر شدن
                cols = st.columns(3)
                col_items = len(available_columns) // 3 + (1 if len(available_columns) % 3 > 0 else 0)

                for i, col_name in enumerate(available_columns):
                    col_idx = i // col_items
                    with cols[col_idx]:
                        if st.checkbox(col_name, value=col_name in st.session_state.selected_columns, key=f"col_{col_name}", label_visibility="visible"):
                            temp_selected.append(col_name)

                # دکمه‌های میانبر در یک ردیف
                button_cols = st.columns(3)
                with button_cols[0]:
                    if st.button("انتخاب همه", use_container_width=True):
                        st.session_state.selected_columns = available_columns
                        st.rerun()

                with button_cols[1]:
                    if st.button("حذف همه", use_container_width=True):
                        st.session_state.selected_columns = ['شناسه', 'نام دارایی']
                        st.rerun()

                with button_cols[2]:
                    if st.button("اعمال تغییرات", use_container_width=True):
                        if temp_selected:
                            st.session_state.selected_columns = temp_selected
                        else:
                            st.session_state.selected_columns = ['شناسه', 'نام دارایی']
                        st.rerun()

            # فیلتر کردن جدول بر اساس ستون‌های انتخاب شده
            if st.session_state.selected_columns:
                filtered_df = display_df[st.session_state.selected_columns]
                # نمایش اطلاعات تعداد ستون‌های انتخاب شده
                if len(st.session_state.selected_columns) < len(available_columns):
                    st.caption(f"🔍 نمایش {len(st.session_state.selected_columns)} ستون از {len(available_columns)} ستون")
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.info("لطفاً حداقل یک ستون را برای نمایش انتخاب کنید.")

            # Allow editing or deleting trades
            st.subheader("ویرایش یا حذف معاملات")

            # ایجاد لیست شناسه‌های معاملات برای انتخاب
            trade_options = []
            for idx, row in trades_df.iterrows():
                description = f"شناسه {row['id']}: {row['jalali_date']} - {row['trade_type']} {row['asset_name']}"
                trade_options.append((row['id'], description))

            if trade_options:
                # ایجاد یک selectbox برای انتخاب شناسه معامله
                selected_trade_id = st.selectbox(
                    "انتخاب شناسه معامله برای ویرایش یا حذف",
                    options=[x[0] for x in trade_options],
                    format_func=lambda x: next((f"شناسه {x}: {row['jalali_date']} - {row['asset_name']}" for id, row in trades_df.iterrows() if row['id'] == x), f"شناسه {x}")
                )

                # Get the selected trade details
                selected_trade = trades_df[trades_df['id'] == selected_trade_id].iloc[0].to_dict()

                # Create tabs for edit and delete operations
                edit_tab, delete_tab = st.tabs(["ویرایش معامله", "حذف معامله"])

                with edit_tab:
                    st.write(f"ویرایش معامله {selected_trade['asset_name']} در تاریخ {selected_trade['jalali_date']}")

                    # Create a form for editing
                    with st.form("edit_trade_form"):
                        # Date picker for editing
                        edit_jalali_date_str = st.text_input(
                            "تاریخ معامله (سال-ماه-روز)", 
                            value=convert_to_jalali(selected_trade['trade_date']).strftime('%Y-%m-%d'),
                            key="edit_jalali_date"
                        )

                        try:
                            # Parse date from text input
                            date_parts = edit_jalali_date_str.split('-')
                            if len(date_parts) == 3:
                                edit_year = int(date_parts[0])
                                edit_month = int(date_parts[1])
                                edit_day = int(date_parts[2])

                                edit_jalali_date = jdatetime.datetime(edit_year, edit_month, edit_day)
                                edit_trade_date = edit_jalali_date.togregorian()
                            else:
                                raise ValueError("فرمت تاریخ صحیح نیست")
                        except ValueError:
                            st.error("تاریخ وارد شده معتبر نیست. لطفاً با فرمت سال-ماه-روز وارد کنید.")
                            edit_trade_date = selected_trade['trade_date']

                        # Asset information (non-editable)
                        st.text(f"نام دارایی: {selected_trade['asset_name']}")
                        st.text(f"نوع دارایی: {selected_trade['asset_type']}")
                        st.text(f"نوع معامله: {selected_trade['trade_type']}")

                        # Editable fields
                        edit_quantity = st.number_input(
                            "تعداد/مقدار", 
                            min_value=0.0, 
                            value=float(selected_trade['quantity']),
                            key="edit_quantity"
                        )

                        # واحد ارزی بالای قیمت واحد
                        current_currency = selected_trade['currency'] if pd.notna(selected_trade['currency']) else "تومان"
                        edit_currency = st.selectbox(
                            "واحد ارزی",
                            options=["تومان", "دلار"],
                            index=0 if current_currency == "تومان" else 1,
                            key="edit_currency"
                        )

                        edit_price = st.number_input(
                            "قیمت واحد", 
                            min_value=0.0, 
                            value=float(selected_trade['price']),
                            key="edit_price"
                        )

                        # Calculate total
                        edit_total_amount = edit_quantity * edit_price
                        st.write(f"مبلغ کل: {format_number(edit_total_amount)} {edit_currency}")

                        # Add is_profit_sale if it's a sell trade
                        edit_is_profit_sale = False
                        if selected_trade['trade_type'] == 'فروش':
                            current_is_profit = selected_trade['is_profit_sale'] if 'is_profit_sale' in selected_trade and pd.notna(selected_trade['is_profit_sale']) else False
                            edit_is_profit_sale = st.checkbox(
                                "این فروش از محل سود معاملات قبلی انجام شده است",
                                value=current_is_profit,
                                key="edit_is_profit_sale_checkbox"
                            )

                        # Notes
                        edit_notes = st.text_area(
                            "توضیحات", 
                            value=selected_trade['notes'] if pd.notna(selected_trade['notes']) else "",
                            key="edit_notes"
                        )

                        # Submit button
                        edit_submitted = st.form_submit_button("ذخیره تغییرات")

                        if edit_submitted:
                            # Update the trade in the database
                            conn = get_connection()
                            cursor = conn.cursor()

                            # Prepare parameters
                            params = {
                                'trade_date': edit_trade_date,
                                'quantity': edit_quantity,
                                'price': edit_price,
                                'total_amount': edit_total_amount,
                                'notes': edit_notes,
                                'currency': edit_currency,
                                'id': selected_trade_id
                            }

                            # Add is_profit_sale if it's a sell trade
                            if selected_trade['trade_type'] == 'فروش':
                                params['is_profit_sale'] = edit_is_profit_sale

                            # Execute update query
                            if USE_SQLITE:
                                if selected_trade['trade_type'] == 'فروش':
                                    cursor.execute('''
                                        UPDATE trades 
                                        SET trade_date = ?, quantity = ?, price = ?, 
                                            total_amount = ?, notes = ?, currency = ?, is_profit_sale = ?
                                        WHERE id = ?
                                    ''', (params['trade_date'], params['quantity'], params['price'], 
                                         params['total_amount'], params['notes'], params['currency'], 
                                         params['is_profit_sale'], params['id']))
                                else:
                                    cursor.execute('''
                                        UPDATE trades 
                                        SET trade_date = ?, quantity = ?, price = ?, 
                                            total_amount = ?, notes = ?, currency = ?
                                        WHERE id = ?
                                    ''', (params['trade_date'], params['quantity'], params['price'], 
                                         params['total_amount'], params['notes'], params['currency'], 
                                         params['id']))
                            else:
                                if selected_trade['trade_type'] == 'فروش':
                                    cursor.execute('''
                                        UPDATE trades 
                                        SET trade_date = %s, quantity = %s, price = %s, 
                                            total_amount = %s, notes = %s, currency = %s, is_profit_sale = %s
                                        WHERE id = %s
                                    ''', (params['trade_date'], params['quantity'], params['price'], 
                                         params['total_amount'], params['notes'], params['currency'], 
                                         params['is_profit_sale'], params['id']))
                                else:
                                    cursor.execute('''
                                        UPDATE trades 
                                        SET trade_date = %s, quantity = %s, price = %s, 
                                            total_amount = %s, notes = %s, currency = %s
                                        WHERE id = %s
                                    ''', (params['trade_date'], params['quantity'], params['price'], 
                                         params['total_amount'], params['notes'], params['currency'], 
                                         params['id']))

                            conn.commit()

                            # Recalculate asset data
                            recalculate_asset_data(selected_trade['asset_name'], selected_trade['asset_type'])

                            conn.close()
                            st.success("معامله با موفقیت ویرایش شد.")
                            st.rerun()

                with delete_tab:
                    st.write(f"حذف معامله {selected_trade['asset_name']} در تاریخ {selected_trade['jalali_date']}")
                    st.warning("توجه: حذف این معامله ممکن است بر روی داده‌های دیگر تأثیر بگذارد.")

                    # Confirm deletion
                    if st.button("تأیید حذف معامله", key="confirm_delete"):
                        # Delete the trade
                        if delete_trade(selected_trade_id):
                            st.success("معامله با موفقیت حذف شد.")
                            st.rerun()
                        else:
                            st.error("خطا در حذف معامله.")

        else:
            st.info("هنوز معامله‌ای ثبت نشده است.")