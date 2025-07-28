#!/bin/bash
# sacred_cli_integration.sh - CLI commands for Sacred Layer operations
# Created: 2025-07-24 03:44:00 (Australia/Sydney)
# Part of: ContextKeeper v3.0 Sacred Layer Upgrade

# Sacred Layer CLI command handler
handle_sacred() {
    local subcommand=$1
    shift

    case "$subcommand" in
        create)
            create_sacred_plan "$@"
            ;;
        approve)
            approve_sacred_plan "$@"
            ;;
        list)
            list_sacred_plans "$@"
            ;;
        query)
            query_sacred_plans "$@"
            ;;
        drift)
            check_sacred_drift "$@"
            ;;
        verify)
            verify_sacred_integrity "$@"
            ;;
        export)
            export_sacred_plans "$@"
            ;;
        import)
            import_sacred_plans "$@"
            ;;
        supersede)
            supersede_sacred_plan "$@"
            ;;
        cleanup)
            cleanup_old_plans "$@"
            ;;
        *)
            echo "Sacred Layer Commands:"
            echo "  sacred create <project_id> <title> <file>  - Create new sacred plan"
            echo "  sacred approve <plan_id>                    - Approve plan (2-layer verification)"
            echo "  sacred list <project_id>                    - List sacred plans for project"
            echo "  sacred query <project_id> <query>           - Query sacred plans"
            echo "  sacred drift <project_id>                   - Check drift against sacred plans"
            echo "  sacred verify                               - Verify sacred database integrity"
            echo "  sacred export <project_id>                  - Export sacred plans"
            echo "  sacred import <project_id> <file>           - Import sacred plans"
            echo "  sacred supersede <old_id> <new_id>          - Supersede old plan with new"
            echo "  sacred cleanup --days <N>                   - Clean up old superseded plans"
            return 1
            ;;
    esac
}

# Create a new sacred plan
create_sacred_plan() {
    local project_id=$1
    local title=$2
    local file_path=$3

    if [ -z "$project_id" ] || [ -z "$title" ] || [ -z "$file_path" ]; then
        echo "Usage: sacred create <project_id> <title> <file_path>"
        return 1
    fi

    if [ ! -f "$file_path" ]; then
        echo "Error: File not found: $file_path"
        return 1
    fi

    echo "Creating sacred plan..."
    echo "Project: $project_id"
    echo "Title: $title"
    echo "File: $file_path"

    # Make API call to create sacred plan
    response=$(curl -s -X POST http://localhost:5555/sacred/plans \
        -H "Content-Type: application/json" \
        -d "{
            \"project_id\": \"$project_id\",
            \"title\": \"$title\",
            \"file_path\": \"$file_path\"
        }")

    # Parse response
    plan_id=$(echo "$response" | jq -r '.plan_id')
    verification_code=$(echo "$response" | jq -r '.verification_code')

    if [ "$plan_id" != "null" ]; then
        echo ""
        echo "✅ Sacred plan created"
        echo "Plan ID: $plan_id"
        echo "Verification Code: $verification_code"
        echo ""
        echo "⚠️  Save this verification code - you'll need it for approval"
    else
        echo "❌ Failed to create sacred plan"
        echo "$response" | jq '.'
    fi
}

# Approve a sacred plan with 2-layer verification
approve_sacred_plan() {
    local plan_id=$1
    
    if [ -z "$plan_id" ]; then
        echo "Usage: sacred approve <plan_id>"
        return 1
    fi
    
    # Prompt for verification code
    echo -n "Enter verification code: "
    read -r verification_code

    # Prompt for secondary verification (environment key)
    echo -n "Enter approval key: "
    read -rs approval_key
    echo ""

    # Get approver name
    approver=$(whoami)

    echo "Approving sacred plan..."

    # Make API call to approve
    response=$(curl -s -X POST "http://localhost:5555/sacred/plans/$plan_id/approve" \
        -H "Content-Type: application/json" \
        -d "{
            \"approver\": \"$approver\",
            \"verification_code\": \"$verification_code\",
            \"secondary_verification\": \"$approval_key\"
        }")

    # Check response
    status=$(echo "$response" | jq -r '.status')

    if [ "$status" = "approved" ]; then
        echo "✅ Sacred plan approved and locked"
        echo "This plan is now immutable and will guide development"
    else
        echo "❌ Failed to approve sacred plan"
        echo "$response" | jq '.'
    fi
}

# Check drift against sacred plans
check_sacred_drift() {
    local project_id=$1
    local detailed=${2:-""}

    if [ -z "$project_id" ]; then
        echo "Usage: sacred drift <project_id> [--detailed]"
        return 1
    fi

    echo "Analyzing sacred drift for project: $project_id"

    # Make API call
    response=$(curl -s "http://localhost:5555/sacred/drift/$project_id")

    # Parse response
    status=$(echo "$response" | jq -r '.status')
    alignment=$(echo "$response" | jq -r '.alignment_score')
    violations=$(echo "$response" | jq -r '.violations | length')

    # Display results with color coding
    case "$status" in
        "aligned")
            echo "✅ Status: aligned"
            ;;
        "minor_drift")
            echo "⚠️  Status: minor_drift"
            ;;
        "moderate_drift")
            echo "🟠 Status: moderate_drift"
            ;;
        "critical_violation")
            echo "🔴 Status: critical_violation"
            ;;
    esac

    echo "Alignment Score: ${alignment}%"
    echo "Violations: $violations"

    if [ "$violations" -gt 0 ]; then
        echo ""
        echo "Plan Adherence:"
        echo "$response" | jq -r '.sacred_plans_checked[] | "  \(.status_icon) \(.plan_id): \(.alignment)%"'
    fi

    # Show recommendations
    echo ""
    echo "Recommendations:"
    echo "$response" | jq -r '.recommendations[] | "  • \(.)"'

    # Detailed view if requested
    if [ "$detailed" = "--detailed" ]; then
        echo ""
        echo "Detailed Violations:"
        echo "$response" | jq '.violations'
    fi
}

# List sacred plans for a project
list_sacred_plans() {
    local project_id=$1

    if [ -z "$project_id" ]; then
        echo "Usage: sacred list <project_id>"
        return 1
    fi

    echo "Sacred Plans for project: $project_id"
    echo ""

    # Make API call
    response=$(curl -s "http://localhost:5555/sacred/plans?project_id=$project_id")

    # Display plans
    echo "$response" | jq -r '.plans[] | "\(.status_icon) [\(.plan_id)] \(.title) - \(.status) (created: \(.created_at))"'
}

# Query sacred plans
query_sacred_plans() {
    local project_id=$1
    local query=$2

    if [ -z "$project_id" ] || [ -z "$query" ]; then
        echo "Usage: sacred query <project_id> <query>"
        return 1
    fi

    echo "Querying sacred plans..."

    # Make API call
    response=$(curl -s -X POST http://localhost:5555/sacred/query \
        -H "Content-Type: application/json" \
        -d "{
            \"project_id\": \"$project_id\",
            \"query\": \"$query\"
        }")

    # Display results
    echo "$response" | jq '.'
}

# Verify sacred database integrity
verify_sacred_integrity() {
    echo "Verifying sacred database integrity..."

    # Make API call
    response=$(curl -s http://localhost:5555/sacred/verify)

    # Display results
    status=$(echo "$response" | jq -r '.status')

    if [ "$status" = "healthy" ]; then
        echo "✅ Sacred database integrity verified"
        echo "$response" | jq '.'
    else
        echo "❌ Sacred database integrity check failed"
        echo "$response" | jq '.'
    fi
}

# Export sacred plans
export_sacred_plans() {
    local project_id=$1
    local format=${2:-"json"}

    if [ -z "$project_id" ]; then
        echo "Usage: sacred export <project_id> [--format markdown|json]"
        return 1
    fi

    echo "Exporting sacred plans for project: $project_id"

    # Make API call
    curl -s "http://localhost:5555/sacred/export?project_id=$project_id&format=$format"
}

# Helper function to display sacred status icons
get_sacred_status_icon() {
    local status=$1

    case "$status" in
        "draft")
            echo "📝"
            ;;
        "pending_approval")
            echo "⏳"
            ;;
        "approved")
            echo "🔒"
            ;;
        "superseded")
            echo "🔄"
            ;;
        "archived")
            echo "📦"
            ;;
        *)
            echo "❓"
            ;;
    esac
}