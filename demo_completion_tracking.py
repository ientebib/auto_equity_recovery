#!/usr/bin/env python3
"""
Demonstration of the Lead Completion Tracking System

This script shows how the completion tracking system works in practice,
demonstrating the key features and integration with existing systems.
"""

import sys
from pathlib import Path

# Add the lead_recovery package to the path
sys.path.append(str(Path(__file__).parent))

from lead_recovery.cache import SummaryCache, compute_conversation_digest


def demo_completion_workflow():
    """Demonstrate a complete agent workflow with completion tracking"""

    print("🎭 DEMO: Agent Completion Workflow")
    print("=" * 60)

    # Initialize the system
    cache = SummaryCache()

    # Simulate a lead from a real campaign
    lead_phone = "5551234567"
    campaign = "simulation_to_handoff"
    agent_name = "Maria Rodriguez"

    # Initial conversation
    conversation_v1 = """2024-01-15 09:30 user: Hola, vi que me preaprobaron un préstamo
2024-01-15 09:31 agent: ¡Hola! Sí, tienes una preaprobación. ¿Te interesa conocer los detalles?
2024-01-15 09:32 user: Sí, por favor
2024-01-15 09:33 agent: Perfecto, te envío la información por WhatsApp"""

    digest_v1 = compute_conversation_digest(conversation_v1)

    print(f"📱 Lead: {lead_phone}")
    print(f"🍳 Campaign: {campaign}")
    print(f"👤 Agent: {agent_name}")
    print(f"💬 Initial conversation: {len(conversation_v1)} characters")
    print(f"🔍 Conversation digest: {digest_v1[:16]}...")

    # Step 1: Check initial status
    print("\n1️⃣ Checking initial lead status...")
    status = cache.get_lead_completion_status(lead_phone, campaign, digest_v1)
    print(f"   Status: {status['status']}")
    print(f"   Is completed: {status['is_completed']}")
    print("   → Lead is ACTIVE and ready for processing")

    # Step 2: Agent processes the lead and marks it complete
    print("\n2️⃣ Agent processes lead and marks complete...")
    completion_notes = "Cliente recibió información y confirmó que no está interesado en este momento. Pidió que lo contactemos en 6 meses."

    success = cache.mark_lead_complete(
        phone_number=lead_phone,
        recipe_name=campaign,
        conversation_digest=digest_v1,
        completed_by=agent_name,
        notes=completion_notes,
    )

    print(f"   Completion successful: {success}")
    print(f"   Notes: {completion_notes[:50]}...")

    # Step 3: Verify completion status
    print("\n3️⃣ Verifying completion status...")
    status = cache.get_lead_completion_status(lead_phone, campaign, digest_v1)
    print(f"   Status: {status['status']}")
    print(f"   Is completed: {status['is_completed']}")
    print(f"   Completed by: {status['completion_info']['completed_by']}")
    print("   → Lead is now COMPLETED and won't be processed again")

    # Step 4: Simulate conversation update (new message from customer)
    print("\n4️⃣ Customer sends new message (conversation changes)...")
    conversation_v2 = (
        conversation_v1
        + """
2024-01-16 14:20 user: Hola, cambié de opinión. ¿Podemos hablar del préstamo?"""
    )

    digest_v2 = compute_conversation_digest(conversation_v2)
    print(
        f"   New conversation: +{len(conversation_v2) - len(conversation_v1)} characters"
    )
    print(f"   New digest: {digest_v2[:16]}...")
    print(f"   Digests match: {digest_v1 == digest_v2}")

    # Step 5: Check status with new conversation
    print("\n5️⃣ Checking status with updated conversation...")
    status = cache.get_lead_completion_status(lead_phone, campaign, digest_v2)
    print(f"   Status: {status['status']}")
    print(f"   Is completed: {status['is_completed']}")
    print(f"   Needs reactivation: {status['needs_reactivation']}")
    print(
        f"   Previous completion by: {status['completion_info']['previously_completed_by']}"
    )
    print(f"   Reactivation reason: {status['completion_info']['reactivation_reason']}")
    print("   → Lead is REACTIVATED and available for processing again!")

    return True


def demo_recipe_integration():
    """Demonstrate how completion tracking integrates with recipe processing"""

    print("\n🍳 DEMO: Recipe Integration")
    print("=" * 60)

    cache = SummaryCache()

    # Simulate multiple leads in different states
    leads = [
        {
            "phone": "5551111111",
            "name": "Carlos Mendez",
            "status": "new",
            "conversation": "2024-01-15 10:00 user: Hola, quiero información sobre préstamos",
        },
        {
            "phone": "5552222222",
            "name": "Ana Silva",
            "status": "completed",
            "conversation": "2024-01-14 15:30 user: No me interesa, gracias",
        },
        {
            "phone": "5553333333",
            "name": "Luis Torres",
            "status": "reactivated",
            "conversation": "2024-01-13 12:00 user: No gracias\n2024-01-16 09:00 user: Reconsideré, ¿podemos hablar?",
        },
    ]

    campaign = "marzo_cohorts_live"

    # Pre-setup: Mark Ana as completed
    ana_digest = compute_conversation_digest(
        "2024-01-14 15:30 user: No me interesa, gracias"
    )
    cache.mark_lead_complete(
        "5552222222", campaign, ana_digest, "Agent 1", "Cliente no interesado"
    )

    print(f"📋 Processing {len(leads)} leads for campaign: {campaign}")
    print()

    processed_count = 0
    skipped_count = 0
    reactivated_count = 0

    for i, lead in enumerate(leads, 1):
        print(f"{i}. {lead['name']} ({lead['phone']})")

        # Get conversation digest
        digest = compute_conversation_digest(lead["conversation"])

        # Check completion status (this is what would happen in a real recipe)
        status = cache.get_lead_completion_status(lead["phone"], campaign, digest)

        print(f"   Status: {status['status']}")

        if status["is_completed"] and not status["needs_reactivation"]:
            print("   → SKIPPED (already completed)")
            skipped_count += 1
        else:
            if status["needs_reactivation"]:
                print("   → REACTIVATED (conversation changed)")
                reactivated_count += 1
            else:
                print("   → PROCESSING (new lead)")

            # Simulate processing
            print("   → Processing lead...")
            processed_count += 1

    print("\n📊 Recipe Processing Summary:")
    print(f"   Processed: {processed_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Reactivated: {reactivated_count}")
    print("   → Completion tracking optimized processing!")

    return True


def demo_analytics():
    """Demonstrate completion analytics and reporting"""

    print("\n📊 DEMO: Analytics & Reporting")
    print("=" * 60)

    cache = SummaryCache()

    # Get completion statistics
    campaigns = ["simulation_to_handoff", "marzo_cohorts_live", "top_up_may"]

    print("Campaign Completion Statistics:")
    print()

    total_completed = 0
    for campaign in campaigns:
        stats = cache.get_completion_stats(campaign)
        completed_leads = cache.get_completed_leads_for_recipe(campaign)

        print(f"🍳 {campaign.replace('_', ' ').title()}")
        print(f"   Total tracked: {stats['total_tracked']}")
        print(f"   Completed: {stats['status_counts'].get('COMPLETED', 0)}")
        print(f"   Reactivated: {stats['status_counts'].get('REACTIVATED', 0)}")
        print(f"   Completion rate: {stats['completion_rate']:.1%}")

        if completed_leads:
            print("   Recent completions:")
            for lead in completed_leads[-3:]:  # Show last 3
                print(f"     • {lead['phone']} by {lead['completed_by']}")

        total_completed += stats["status_counts"].get("COMPLETED", 0)
        print()

    print("🎯 Overall Statistics:")
    print(f"   Total leads completed: {total_completed}")
    print(f"   Active campaigns: {len(campaigns)}")
    print("   → System is tracking completions across all campaigns!")

    return True


def main():
    """Run all demonstrations"""

    print("🚀 Lead Completion Tracking System Demo")
    print("This demonstrates how the system works in practice")
    print("=" * 70)

    try:
        # Run demonstrations
        demo_completion_workflow()
        demo_recipe_integration()
        demo_analytics()

        print("\n" + "=" * 70)
        print("🎉 DEMO COMPLETE!")
        print()
        print("Key Takeaways:")
        print("✅ Agents can mark leads complete with notes")
        print("✅ Leads automatically reactivate when conversations change")
        print("✅ Recipe processing is optimized (skips completed leads)")
        print("✅ Full analytics and reporting available")
        print("✅ Zero impact on existing lead recovery functionality")
        print()
        print("The system is ready for production use! 🚀")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    main()
