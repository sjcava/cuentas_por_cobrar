import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import re
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import base64

# Configuración de la página
st.set_page_config(
    page_title="Dashboard Cuentas por Cobrar - Locatel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Colores de Locatel
COLORS = {
    'yellow': '#FED519',
    'orange': '#F79617',
    'light_green': '#7CC141',
    'medium_green': '#419E46',
    'dark_green': '#0A9561'
}

# CSS personalizado mejorado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0A9561 0%, #419E46 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 4px solid #0A9561;
    }

    .alert-danger {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }

    .alert-success {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }

    .alert-info {
        background: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }

    .filter-section {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }

    .download-section {
        background: linear-gradient(135deg, #FED519 0%, #F79617 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_and_process_data(file_path):
    """Cargar y procesar datos del CSV"""
    try:
        # Leer archivo CSV
        if isinstance(file_path, str):
            df = pd.read_csv(file_path, sep=';', encoding='latin-1')
        else:
            df = pd.read_csv(file_path, sep=';', encoding='latin-1')

        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()

        # Limpiar datos
        df['Fecha de documento'] = df['Fecha de documento'].str.strip()
        df['Texto'] = df['Texto'].str.strip()
        df['Importe valorado ML2'] = df['Importe valorado ML2'].str.strip()
        df['Importe valorado ML2'] = df['Importe valorado ML2'].str.replace(',', '.')

        # Filtrar filas válidas
        df = df[df['Importe valorado ML2'] != '']
        df = df[df['Importe valorado ML2'].notna()]

        # Convertir a numérico
        df['Importe valorado ML2'] = pd.to_numeric(df['Importe valorado ML2'], errors='coerce')
        df = df.dropna(subset=['Importe valorado ML2'])

        # Filtrar solo valores positivos
        df_positivos = df[df['Importe valorado ML2'] > 0].copy()

        # Convertir fechas
        def parse_date(date_str):
            try:
                return pd.to_datetime(date_str, format='%d/%m/%y')
            except:
                try:
                    return pd.to_datetime(date_str, format='%d/%m/%Y')
                except:
                    return None

        df_positivos['Fecha'] = df_positivos['Fecha de documento'].apply(parse_date)
        df_positivos = df_positivos.dropna(subset=['Fecha'])

        # Calcular días de antigüedad
        today = datetime.now()
        df_positivos['Dias_Antiguedad'] = (today - df_positivos['Fecha']).dt.days

        # Extraer nombres de clientes
        def extract_client_name(text):
            text = str(text).upper()
            patterns_to_remove = [
                r'SALDO FAV PAG D FT \d+',
                r'FT \d+',
                r'\(.*?\)',
                r'TARJ\. CREDIT COMISION',
                r'CORPORACION CARD'
            ]

            for pattern in patterns_to_remove:
                text = re.sub(pattern, '', text)

            text = ' '.join(text.split())
            return text.strip()

        df_positivos['Cliente'] = df_positivos['Texto'].apply(extract_client_name)

        # Categorizar antigüedad
        def categorize_aging(days):
            if days <= 30:
                return '0-30 días'
            elif days <= 60:
                return '31-60 días'
            elif days <= 90:
                return '61-90 días'
            else:
                return 'Más de 90 días'

        df_positivos['Categoria_Antiguedad'] = df_positivos['Dias_Antiguedad'].apply(categorize_aging)

        # Categorizar riesgo
        def categorize_risk(days, amount):
            if days > 90 and amount > 50:
                return 'Alto'
            elif days > 60 or amount > 100:
                return 'Medio'
            else:
                return 'Bajo'

        df_positivos['Riesgo'] = df_positivos.apply(
            lambda x: categorize_risk(x['Dias_Antiguedad'], x['Importe valorado ML2']), axis=1
        )

        # Agregar columnas adicionales para análisis
        df_positivos['Mes'] = df_positivos['Fecha'].dt.to_period('M')
        df_positivos['Trimestre'] = df_positivos['Fecha'].dt.to_period('Q')

        return df_positivos

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None

def apply_filters(df, date_range, amount_range, aging_filter, risk_filter, client_filter):
    """Aplicar filtros al dataframe"""
    filtered_df = df.copy()

    # Filtro por fecha
    if date_range:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['Fecha'].dt.date >= start_date) & 
            (filtered_df['Fecha'].dt.date <= end_date)
        ]

    # Filtro por monto
    if amount_range:
        min_amount, max_amount = amount_range
        filtered_df = filtered_df[
            (filtered_df['Importe valorado ML2'] >= min_amount) & 
            (filtered_df['Importe valorado ML2'] <= max_amount)
        ]

    # Filtro por antigüedad
    if aging_filter and aging_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Categoria_Antiguedad'] == aging_filter]

    # Filtro por riesgo
    if risk_filter and risk_filter != "Todos":
        filtered_df = filtered_df[filtered_df['Riesgo'] == risk_filter]

    # Filtro por cliente
    if client_filter:
        filtered_df = filtered_df[filtered_df['Cliente'].str.contains(client_filter, case=False, na=False)]

    return filtered_df

def calculate_metrics(df):
    """Calcular métricas principales"""
    if df is None or df.empty:
        return {}

    return {
        'total_facturas': len(df),
        'monto_total': df['Importe valorado ML2'].sum(),
        'clientes_unicos': df['Cliente'].nunique(),
        'promedio_factura': df['Importe valorado ML2'].mean(),
        'promedio_dias': df['Dias_Antiguedad'].mean(),
        'mediana_monto': df['Importe valorado ML2'].median(),
        'monto_max': df['Importe valorado ML2'].max(),
        'monto_min': df['Importe valorado ML2'].min()
    }

def create_aging_chart(df):
    """Crear gráfico de antigüedad"""
    aging_data = df.groupby('Categoria_Antiguedad')['Importe valorado ML2'].sum().reset_index()

    fig = px.pie(
        aging_data, 
        values='Importe valorado ML2', 
        names='Categoria_Antiguedad',
        title="Distribución por Antigüedad",
        color_discrete_sequence=[COLORS['dark_green'], COLORS['medium_green'], COLORS['orange'], '#dc3545']
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=400)

    return fig

def create_trend_chart(df):
    """Crear gráfico de tendencias mensuales"""
    monthly_data = df.groupby('Mes')['Importe valorado ML2'].sum().reset_index()
    monthly_data['Mes_str'] = monthly_data['Mes'].astype(str)

    fig = px.line(
        monthly_data,
        x='Mes_str',
        y='Importe valorado ML2',
        title="Tendencia Mensual de Cuentas por Cobrar",
        markers=True
    )

    fig.update_traces(line_color=COLORS['medium_green'], marker_color=COLORS['dark_green'])
    fig.update_layout(height=400)

    return fig

def create_risk_chart(df):
    """Crear gráfico de riesgo"""
    risk_data = df.groupby('Riesgo')['Importe valorado ML2'].sum().reset_index()

    fig = px.bar(
        risk_data,
        x='Riesgo',
        y='Importe valorado ML2',
        title="Análisis de Riesgo",
        color='Riesgo',
        color_discrete_map={'Alto': '#dc3545', 'Medio': COLORS['orange'], 'Bajo': COLORS['light_green']}
    )

    fig.update_layout(height=400, showlegend=False)
    fig.update_traces(texttemplate='$%{y:,.0f}', textposition='outside')

    return fig

def create_clients_chart(df, top_n=10):
    """Crear gráfico de top clientes"""
    top_clients = df.groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False).head(top_n)

    fig = px.bar(
        x=top_clients.values,
        y=top_clients.index,
        orientation='h',
        title=f"Top {top_n} Clientes por Monto",
        labels={'x': 'Monto ($)', 'y': 'Cliente'}
    )

    fig.update_traces(marker_color=COLORS['medium_green'])
    fig.update_layout(height=500)

    return fig

def generate_pdf_report(df, metrics):
    """Generar reporte PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#0A9561')
    )
    story.append(Paragraph("Reporte de Cuentas por Cobrar - Locatel", title_style))
    story.append(Spacer(1, 12))

    # Fecha del reporte
    story.append(Paragraph(f"Fecha del reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 20))

    # Métricas principales
    story.append(Paragraph("Métricas Principales", styles['Heading2']))

    metrics_data = [
        ['Métrica', 'Valor'],
        ['Total de Facturas', f"{metrics['total_facturas']:,}"],
        ['Monto Total', f"${metrics['monto_total']:,.2f}"],
        ['Clientes Únicos', f"{metrics['clientes_unicos']:,}"],
        ['Promedio por Factura', f"${metrics['promedio_factura']:,.2f}"],
        ['Días Promedio', f"{metrics['promedio_dias']:.1f}"],
        ['Monto Máximo', f"${metrics['monto_max']:,.2f}"],
        ['Monto Mínimo', f"${metrics['monto_min']:,.2f}"]
    ]

    metrics_table = Table(metrics_data)
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0A9561')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(metrics_table)
    story.append(Spacer(1, 20))

    # Top 10 clientes
    story.append(Paragraph("Top 10 Clientes", styles['Heading2']))

    top_clients = df.groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False).head(10)
    clients_data = [['Cliente', 'Monto']]
    for client, amount in top_clients.items():
        clients_data.append([client[:50] + '...' if len(client) > 50 else client, f"${amount:,.2f}"])

    clients_table = Table(clients_data)
    clients_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#419E46')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(clients_table)

    doc.build(story)
    buffer.seek(0)
    return buffer

def create_excel_report(df, metrics):
    """Generar reporte Excel"""
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Hoja de métricas
        metrics_df = pd.DataFrame([
            ['Total de Facturas', metrics['total_facturas']],
            ['Monto Total', metrics['monto_total']],
            ['Clientes Únicos', metrics['clientes_unicos']],
            ['Promedio por Factura', metrics['promedio_factura']],
            ['Días Promedio', metrics['promedio_dias']],
            ['Monto Máximo', metrics['monto_max']],
            ['Monto Mínimo', metrics['monto_min']]
        ], columns=['Métrica', 'Valor'])

        metrics_df.to_excel(writer, sheet_name='Métricas', index=False)

        # Hoja de datos completos
        df_export = df[['Fecha de documento', 'Cliente', 'Importe valorado ML2', 
                       'Dias_Antiguedad', 'Categoria_Antiguedad', 'Riesgo']].copy()
        df_export.to_excel(writer, sheet_name='Datos Completos', index=False)

        # Hoja de análisis de antigüedad
        aging_analysis = df.groupby('Categoria_Antiguedad').agg({
            'Importe valorado ML2': ['sum', 'count', 'mean']
        }).round(2)
        aging_analysis.to_excel(writer, sheet_name='Análisis Antigüedad')

        # Hoja de top clientes
        top_clients = df.groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False).head(20)
        top_clients.to_excel(writer, sheet_name='Top Clientes')

    buffer.seek(0)
    return buffer

# Función principal
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Dashboard Avanzado Cuentas por Cobrar - Locatel</h1>
        <p>Análisis completo con filtros y exportación - Julio 2025</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar para cargar archivo y filtros
    st.sidebar.header("📁 Cargar Datos")
    uploaded_file = st.sidebar.file_uploader(
        "Selecciona el archivo CSV",
        type=['csv'],
        help="Sube tu archivo de cuentas por cobrar en formato CSV"
    )

    # Cargar datos
    if uploaded_file is not None:
        df = load_and_process_data(uploaded_file)
    else:
        st.sidebar.info("💡 Sube tu archivo CSV para comenzar el análisis.")
        df = None

    # Si tenemos datos, mostrar filtros y dashboard
    if df is not None and not df.empty:

        # Sección de filtros en sidebar
        st.sidebar.header("🔍 Filtros Avanzados")

        # Filtro por fecha
        min_date = df['Fecha'].min().date()
        max_date = df['Fecha'].max().date()

        date_range = st.sidebar.date_input(
            "Rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        # Filtro por monto
        min_amount = float(df['Importe valorado ML2'].min())
        max_amount = float(df['Importe valorado ML2'].max())

        amount_range = st.sidebar.slider(
            "Rango de montos ($)",
            min_value=min_amount,
            max_value=max_amount,
            value=(min_amount, max_amount),
            step=1.0
        )

        # Filtro por antigüedad
        aging_options = ["Todos"] + list(df['Categoria_Antiguedad'].unique())
        aging_filter = st.sidebar.selectbox("Categoría de antigüedad", aging_options)

        # Filtro por riesgo
        risk_options = ["Todos"] + list(df['Riesgo'].unique())
        risk_filter = st.sidebar.selectbox("Nivel de riesgo", risk_options)

        # Filtro por cliente
        client_filter = st.sidebar.text_input("Buscar cliente (nombre parcial)")

        # Aplicar filtros
        if len(date_range) == 2:
            filtered_df = apply_filters(df, date_range, amount_range, aging_filter, risk_filter, client_filter)
        else:
            filtered_df = apply_filters(df, None, amount_range, aging_filter, risk_filter, client_filter)

        # Mostrar información de filtros aplicados
        if len(filtered_df) != len(df):
            st.markdown(f"""
            <div class="alert-info">
                <strong>📊 Filtros aplicados:</strong> Mostrando {len(filtered_df):,} de {len(df):,} registros 
                ({len(filtered_df)/len(df)*100:.1f}% del total)
            </div>
            """, unsafe_allow_html=True)

        # Calcular métricas
        metrics = calculate_metrics(filtered_df)

        # Sección de exportación
        st.sidebar.header("📥 Exportar Reportes")

        col1, col2 = st.sidebar.columns(2)

        with col1:
            if st.button("📄 PDF", use_container_width=True):
                pdf_buffer = generate_pdf_report(filtered_df, metrics)
                st.sidebar.download_button(
                    label="Descargar PDF",
                    data=pdf_buffer,
                    file_name=f"reporte_cxc_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

        with col2:
            if st.button("📊 Excel", use_container_width=True):
                excel_buffer = create_excel_report(filtered_df, metrics)
                st.sidebar.download_button(
                    label="Descargar Excel",
                    data=excel_buffer,
                    file_name=f"reporte_cxc_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # Pestañas principales
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Resumen", "⏰ Antigüedad", "👥 Top Clientes", "⚠️ Análisis de Riesgo", "📈 Tendencias"])

        with tab1:
            st.header("Métricas Principales")

            # Métricas en columnas
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Facturas", f"{metrics['total_facturas']:,}")
                st.metric("Monto Máximo", f"${metrics['monto_max']:,.2f}")

            with col2:
                st.metric("Monto Total", f"${metrics['monto_total']:,.2f}")
                st.metric("Monto Mínimo", f"${metrics['monto_min']:,.2f}")

            with col3:
                st.metric("Clientes Únicos", f"{metrics['clientes_unicos']:,}")
                st.metric("Mediana", f"${metrics['mediana_monto']:,.2f}")

            with col4:
                st.metric("Promedio/Factura", f"${metrics['promedio_factura']:,.2f}")
                st.metric("Días Promedio", f"{metrics['promedio_dias']:.1f}")

            # Gráficos en columnas
            col1, col2 = st.columns(2)

            with col1:
                fig_aging = create_aging_chart(filtered_df)
                st.plotly_chart(fig_aging, use_container_width=True)

            with col2:
                fig_risk = create_risk_chart(filtered_df)
                st.plotly_chart(fig_risk, use_container_width=True)

        with tab2:
            st.header("Análisis de Antigüedad")

            # Tabla de antigüedad
            aging_summary = filtered_df.groupby('Categoria_Antiguedad').agg({
                'Importe valorado ML2': ['sum', 'count', 'mean']
            }).round(2)

            aging_summary.columns = ['Monto Total', 'Cantidad', 'Promedio']
            aging_summary['Porcentaje'] = (aging_summary['Monto Total'] / metrics['monto_total'] * 100).round(1)

            st.dataframe(aging_summary, use_container_width=True)

            # Gráfico de barras detallado
            aging_detail = filtered_df.groupby('Categoria_Antiguedad')['Importe valorado ML2'].sum().reset_index()
            fig_aging_detail = px.bar(
                aging_detail,
                x='Categoria_Antiguedad',
                y='Importe valorado ML2',
                title="Monto por Período de Antigüedad",
                color='Categoria_Antiguedad',
                color_discrete_sequence=[COLORS['dark_green'], COLORS['medium_green'], COLORS['orange'], '#dc3545']
            )
            fig_aging_detail.update_layout(showlegend=False)
            st.plotly_chart(fig_aging_detail, use_container_width=True)

        with tab3:
            st.header("Top Clientes")

            # Control para número de clientes a mostrar
            top_n = st.slider("Número de clientes a mostrar", 5, 50, 10)

            # Gráfico de top clientes
            fig_clients = create_clients_chart(filtered_df, top_n)
            st.plotly_chart(fig_clients, use_container_width=True)

            # Tabla de top clientes
            top_clients_table = filtered_df.groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False).head(top_n)
            top_clients_df = pd.DataFrame({
                'Cliente': top_clients_table.index,
                'Monto Pendiente': top_clients_table.values,
                '% del Total': (top_clients_table.values / metrics['monto_total'] * 100).round(1)
            })

            st.dataframe(top_clients_df, use_container_width=True)

        with tab4:
            st.header("Análisis de Riesgo")

            # Alertas
            facturas_90_dias = len(filtered_df[filtered_df['Dias_Antiguedad'] > 90])
            if facturas_90_dias > 0:
                st.markdown(f"""
                <div class="alert-danger">
                    <strong>⚠️ Alerta Crítica:</strong> {facturas_90_dias} facturas con más de 90 días requieren atención inmediata.
                </div>
                """, unsafe_allow_html=True)

            # Métricas de riesgo
            risk_summary = filtered_df.groupby('Riesgo')['Importe valorado ML2'].sum()

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("🔴 Riesgo Alto", f"${risk_summary.get('Alto', 0):,.2f}")

            with col2:
                st.metric("🟡 Riesgo Medio", f"${risk_summary.get('Medio', 0):,.2f}")

            with col3:
                st.metric("🟢 Riesgo Bajo", f"${risk_summary.get('Bajo', 0):,.2f}")

            # Gráfico de riesgo detallado
            fig_risk_detail = create_risk_chart(filtered_df)
            st.plotly_chart(fig_risk_detail, use_container_width=True)

            # Tabla de clientes de alto riesgo
            high_risk_clients = filtered_df[filtered_df['Riesgo'] == 'Alto'].groupby('Cliente')['Importe valorado ML2'].sum().sort_values(ascending=False)

            if not high_risk_clients.empty:
                st.subheader("🚨 Clientes de Alto Riesgo")
                st.dataframe(high_risk_clients.to_frame('Monto'), use_container_width=True)

            # Recomendaciones
            st.markdown("""
            <div class="alert-success">
                <strong>💡 Recomendaciones:</strong>
                <ul>
                    <li>Contactar inmediatamente clientes con facturas > 90 días</li>
                    <li>Implementar recordatorios automáticos a los 45 días</li>
                    <li>Revisar términos de crédito para nuevos clientes</li>
                    <li>Considerar descuentos por pronto pago</li>
                    <li>Establecer límites de crédito más estrictos</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with tab5:
            st.header("Análisis de Tendencias")

            # Gráfico de tendencias mensuales
            if len(filtered_df['Mes'].unique()) > 1:
                fig_trend = create_trend_chart(filtered_df)
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("Se necesitan datos de múltiples meses para mostrar tendencias.")

            # Análisis por trimestre
            quarterly_data = filtered_df.groupby('Trimestre').agg({
                'Importe valorado ML2': ['sum', 'count', 'mean']
            }).round(2)

            if not quarterly_data.empty:
                st.subheader("Análisis Trimestral")
                quarterly_data.columns = ['Monto Total', 'Cantidad', 'Promedio']
                st.dataframe(quarterly_data, use_container_width=True)

            # Distribución de montos
            st.subheader("Distribución de Montos")
            fig_hist = px.histogram(
                filtered_df,
                x='Importe valorado ML2',
                nbins=30,
                title="Distribución de Montos de Facturas"
            )
            fig_hist.update_traces(marker_color=COLORS['medium_green'])
            st.plotly_chart(fig_hist, use_container_width=True)

    else:
        st.info("📁 Por favor, sube un archivo CSV para comenzar el análisis.")

        # Mostrar ejemplo de formato esperado
        st.subheader("Formato de archivo esperado:")
        example_data = pd.DataFrame({
            'Fecha de documento': ['18/2/25', '19/2/25', '22/2/25'],
            'Texto': ['CLIENTE A', 'CLIENTE B', 'CLIENTE C'],
            'Importe valorado ML2': ['27,30', '53,44', '47,86']
        })
        st.dataframe(example_data)

if __name__ == "__main__":
    main()
