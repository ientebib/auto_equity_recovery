#!/usr/bin/env python3
"""
Demo data generator for Lead Recovery Dashboard

This script generates sample lead analysis data to demonstrate
the dashboard functionality when no real analysis data exists.
"""

import pandas as pd
import random
from datetime import datetime, timedelta
from pathlib import Path
import uuid

def generate_demo_data(num_leads: int = 100) -> pd.DataFrame:
    """Generate realistic demo lead data."""
    
    # Sample data for realistic leads
    first_names = [
        "María", "José", "Carlos", "Ana", "Luis", "Carmen", "Francisco", "Elena", "Manuel", "Laura",
        "Antonio", "Isabel", "David", "Rosa", "Miguel", "Pilar", "Jesús", "Dolores", "Alejandro", "Mercedes",
        "Daniel", "Josefa", "Rafael", "Antonia", "Javier", "Teresa", "Fernando", "Patricia", "Sergio", "Cristina"
    ]
    
    last_names = [
        "García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Martín",
        "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso", "Gutiérrez",
        "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Ramírez", "Serrano", "Blanco", "Suárez"
    ]
    
    domains = ["gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "icloud.com"]
    
    # Next action codes with realistic distribution
    action_codes = {
        "LLAMAR_LEAD": 0.20,        # High priority
        "CONTACTO_PRIORITARIO": 0.08,  # High priority
        "MANEJAR_OBJECION": 0.15,   # Medium priority
        "INSISTIR": 0.12,           # Medium priority
        "CERRAR": 0.25,             # Low priority
        "ESPERAR": 0.10,            # Low priority
        "ENVIAR_PLANTILLA_RECUPERACION": 0.10  # Low priority
    }
    
    # Stall reason codes with realistic distribution
    stall_reasons = {
        "NUNCA_RESPONDIO": 0.30,
        "GHOSTING": 0.15,
        "DESINTERES_EXPLICITO": 0.12,
        "PROBLEMA_TERMINOS": 0.10,
        "PROCESO_EN_CURSO": 0.08,
        "FINANCIAMIENTO_ACTIVO": 0.07,
        "PROBLEMA_SEGUNDA_LLAVE": 0.05,
        "NO_PROPIETARIO": 0.04,
        "ZONA_NO_CUBIERTA": 0.03,
        "VEHICULO_ANTIGUO_KM": 0.03,
        "OTRO": 0.03
    }
    
    # Generate leads
    leads = []
    
    for i in range(num_leads):
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        
        # Generate email
        email_base = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}"
        email = f"{email_base}@{random.choice(domains)}"
        
        # Generate phone (Mexican format)
        phone = f"{random.randint(52, 99)}{random.randint(10000000, 99999999)}"
        
        # Generate lead creation time (last 30 days)
        lead_created = datetime.now() - timedelta(days=random.randint(1, 30))
        
        # Generate last message times
        hours_since_last = random.randint(1, 720)  # Up to 30 days
        minutes_since_last = random.randint(0, 59)
        
        # User message timing (some never responded)
        never_responded = random.random() < 0.3
        if never_responded:
            hours_since_user = None
            no_user_messages = True
        else:
            hours_since_user = random.randint(hours_since_last, hours_since_last + 24)
            no_user_messages = False
        
        # Select action and stall reason based on weights
        action_code = random.choices(
            list(action_codes.keys()), 
            weights=list(action_codes.values())
        )[0]
        
        stall_reason = random.choices(
            list(stall_reasons.keys()),
            weights=list(stall_reasons.values())
        )[0]
        
        # Generate appropriate summary based on stall reason
        summaries = {
            "NUNCA_RESPONDIO": f"Cliente nunca respondió al contacto inicial tras oferta preaprobada.",
            "GHOSTING": f"Cliente dejó de responder hace {hours_since_last}h sin causa aparente.",
            "DESINTERES_EXPLICITO": f"Cliente declinó explícitamente la oferta.",
            "PROBLEMA_TERMINOS": f"Cliente cuestiona tasas y términos del préstamo.",
            "PROCESO_EN_CURSO": f"Conversación activa, esperando respuesta del cliente.",
            "FINANCIAMIENTO_ACTIVO": f"Vehículo tiene financiamiento activo pendiente.",
            "PROBLEMA_SEGUNDA_LLAVE": f"Cliente no cuenta con la segunda llave del vehículo.",
            "NO_PROPIETARIO": f"Cliente no es el propietario registrado del vehículo.",
            "ZONA_NO_CUBIERTA": f"Cliente se encuentra en zona no cubierta por Kuna.",
            "VEHICULO_ANTIGUO_KM": f"Vehículo no cumple requisitos de año y kilometraje.",
            "OTRO": f"Motivo de estancamiento no categorizado claramente."
        }
        
        # Generate suggested messages for actionable leads
        suggested_messages = {
            "LLAMAR_LEAD": "",
            "CONTACTO_PRIORITARIO": f"Hola {first_name}, necesitamos resolver tu consulta urgente. ¿Cuándo podemos hablar?",
            "MANEJAR_OBJECION": f"Hola {first_name}, entiendo tus dudas. ¿Te gustaría revisar otras opciones que se adapten mejor?",
            "INSISTIR": f"¡Hola {first_name}! ¿Pudiste revisar nuestra propuesta? Estoy aquí para resolver cualquier duda.",
            "CERRAR": "",
            "ESPERAR": "",
            "ENVIAR_PLANTILLA_RECUPERACION": ""
        }
        
        # Recovery flags
        is_recovery_eligible = hours_since_last >= 24 if not never_responded else False
        is_within_reactivation = hours_since_last < 24 if not never_responded else False
        
        # Sample conversation messages
        user_messages = [
            "Me interesa el préstamo con garantía de mi auto",
            "¿Cuáles son los requisitos?",
            "¿Qué tasa de interés manejan?",
            "Necesito más información sobre los pagos",
            "¿En cuánto tiempo me aprueban?",
            "De momento no, gracias",
            "Está muy alta la tasa",
            "Lo voy a pensar"
        ]
        
        kuna_messages = [
            "¡Hola! Gracias por tu interés en Kuna AutoEquity. Te ayudo con tu préstamo personal.",
            "Los requisitos son: auto a tu nombre, completamente pagado y con segunda llave.",
            "La tasa depende de varios factores. Te puedo generar una cotización personalizada.",
            "Los pagos son mensuales y puedes elegir el plazo que mejor te convenga.",
            "El proceso de aprobación toma entre 24-48 horas hábiles.",
            "Entiendo. Si cambias de opinión, aquí estaré para ayudarte.",
            "Podemos revisar diferentes opciones de plazo para ajustar la mensualidad.",
            "Perfecto. Cuando estés listo, podemos continuar con el proceso."
        ]
        
        lead = {
            "lead_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "clean_email": email,
            "lead_created_at": lead_created.strftime("%Y-%m-%d %H:%M:%S"),
            "name": first_name,
            "last_name": last_name,
            "cleaned_phone": phone,
            "NO_USER_MESSAGES_EXIST": no_user_messages,
            "summary": summaries.get(stall_reason, "Conversación en análisis."),
            "primary_stall_reason_code": stall_reason,
            "next_action_code": action_code,
            "suggested_message_es": suggested_messages.get(action_code, ""),
            "HOURS_MINUTES_SINCE_LAST_USER_MESSAGE": f"{hours_since_user}h {random.randint(0, 59)}m" if hours_since_user else "",
            "HOURS_MINUTES_SINCE_LAST_MESSAGE": f"{hours_since_last}h {minutes_since_last}m",
            "human_transfer": random.random() < 0.1,  # 10% have human transfer
            "transfer_context_analysis": "Cliente requirió escalación por consulta compleja." if random.random() < 0.1 else "",
            "handoff_invitation_detected": random.choice([True, False]),
            "handoff_response": random.choice(["NO_INVITATION", "UNCLEAR_RESPONSE", "NO_RESPONSE"]),
            "handoff_finalized": random.choice([True, False]),
            "IS_WITHIN_REACTIVATION_WINDOW": is_within_reactivation,
            "IS_RECOVERY_PHASE_ELIGIBLE": is_recovery_eligible,
            "last_user_message_text": random.choice(user_messages) if not never_responded else "",
            "last_kuna_message_text": random.choice(kuna_messages),
            "last_message_sender": random.choice(["user", "kuna"])
        }
        
        leads.append(lead)
    
    return pd.DataFrame(leads)

def save_demo_data(df: pd.DataFrame, recipe_name: str = "demo_leads"):
    """Save demo data to the expected output directory structure."""
    
    # Create output directory structure
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "output_run" / recipe_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with current date
    today = datetime.now().strftime("%Y%m%d")
    filename = f"{recipe_name}_analysis_{today}.csv"
    
    # Save main file
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)
    
    # Create symlink to latest
    latest_path = output_dir / "latest.csv"
    if latest_path.exists():
        latest_path.unlink()
    latest_path.symlink_to(filename)
    
    print(f"✅ Demo data saved to: {filepath}")
    print(f"📊 Generated {len(df)} leads")
    print(f"🔗 Latest file: {latest_path}")
    
    return filepath

def main():
    """Generate and save demo data."""
    print("🎭 Lead Recovery Demo Data Generator")
    print("=" * 50)
    
    try:
        num_leads = int(input("Enter number of leads to generate (default 150): ") or "150")
    except ValueError:
        num_leads = 150
    
    print(f"\n🏭 Generating {num_leads} demo leads...")
    
    # Generate data
    df = generate_demo_data(num_leads)
    
    # Show statistics
    print("\n📊 Generated Data Statistics:")
    print(f"  • Total leads: {len(df)}")
    print(f"  • High priority actions: {len(df[df['next_action_code'].isin(['CONTACTO_PRIORITARIO', 'LLAMAR_LEAD'])])}")
    print(f"  • Never responded: {len(df[df['NO_USER_MESSAGES_EXIST'] == True])}")
    print(f"  • Recovery eligible: {len(df[df['IS_RECOVERY_PHASE_ELIGIBLE'] == True])}")
    
    print("\n💾 Saving demo data...")
    save_demo_data(df)
    
    print("\n🚀 Ready to test dashboard!")
    print("Run: python run_dashboard.py")

if __name__ == "__main__":
    main() 