import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def create_asset_allocation_chart(portfolio_data):
    """
    Create a pie chart showing asset allocation.
    
    Args:
        portfolio_data (pd.DataFrame): DataFrame with asset_name and total_value columns
        
    Returns:
        plotly.graph_objects.Figure: Pie chart figure
    """
    fig = px.pie(
        portfolio_data, 
        values='total_value', 
        names='asset_name', 
        title='ترکیب دارایی‌ها',
        labels={'asset_name': 'نام دارایی', 'total_value': 'ارزش کل'}
    )
    
    fig.update_layout(
        font=dict(family="Arial", size=14),
        legend=dict(font=dict(size=12))
    )
    
    return fig

def create_performance_chart(assets_df):
    """
    Create a bar chart showing asset performance.
    
    Args:
        assets_df (pd.DataFrame): DataFrame with asset performance data
        
    Returns:
        plotly.graph_objects.Figure: Bar chart figure
    """
    fig = px.bar(
        assets_df, 
        x='asset_name', 
        y='profit_loss_pct',
        color='profit_loss_pct',
        color_continuous_scale=['red', 'green'],
        labels={'asset_name': 'دارایی', 'profit_loss_pct': 'بازدهی (%)'},
        title='عملکرد دارایی‌ها (درصد)'
    )
    
    fig.update_layout(
        xaxis_title="دارایی",
        yaxis_title="بازدهی (%)",
        font=dict(family="Arial", size=14)
    )
    
    return fig

def create_monthly_pnl_chart(trades_df):
    """
    Create a bar chart showing monthly profit/loss.
    
    Args:
        trades_df (pd.DataFrame): DataFrame with trade data
        
    Returns:
        plotly.graph_objects.Figure: Bar chart figure
    """
    # Extract year and month for grouping
    trades_df['year_month'] = trades_df['trade_date'].dt.strftime('%Y-%m')
    
    # Calculate realized profit/loss by month
    monthly_pnl = trades_df[trades_df['trade_type'] == 'فروش'].groupby('year_month').agg({
        'profit_loss': 'sum'
    }).reset_index()
    
    fig = px.bar(
        monthly_pnl, 
        x='year_month', 
        y='profit_loss',
        color='profit_loss',
        color_continuous_scale=['red', 'green'],
        labels={'year_month': 'ماه', 'profit_loss': 'سود/زیان'},
        title='سود/زیان ماهانه'
    )
    
    fig.update_layout(
        xaxis_title="ماه",
        yaxis_title="سود/زیان (تومان)",
        font=dict(family="Arial", size=14)
    )
    
    return fig

def create_trade_count_chart(trades_df):
    """
    Create a pie chart showing trade count by asset.
    
    Args:
        trades_df (pd.DataFrame): DataFrame with trade data
        
    Returns:
        plotly.graph_objects.Figure: Pie chart figure
    """
    trade_counts = trades_df.groupby('asset_name').size().reset_index(name='count')
    
    fig = px.pie(
        trade_counts, 
        values='count', 
        names='asset_name', 
        title='تعداد معاملات بر اساس دارایی'
    )
    
    fig.update_layout(
        font=dict(family="Arial", size=14),
        legend=dict(font=dict(size=12))
    )
    
    return fig
