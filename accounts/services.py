from .models import CustomerProfile


def update_trust_score(
    user,
    action
):

    profile = CustomerProfile.objects.get(
        user=user
    )

    if action == "completed":
        profile.trust_score += 1
        profile.total_completed_orders += 1

    elif action == "cancelled":
        profile.trust_score -= 10
        profile.total_cancelled_orders += 1

    elif action == "rejected":
        profile.trust_score -= 3
        profile.total_rejected_orders += 1

    elif action == "fake":
        profile.trust_score -= 25

    if profile.trust_score < 50:
        profile.is_flagged = True

    profile.save()