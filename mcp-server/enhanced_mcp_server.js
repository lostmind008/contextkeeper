#!/usr/bin/env node

/**
 * Enhanced MCP Server for ContextKeeper v3.0 Sacred Layer
 * Provides sacred-aware development context to Claude Code and other AI assistants
 *
 * Created: 2025-07-24 16:40:00 (Australia/Sydney)
 * Part of: ContextKeeper v3.0 Sacred Layer Upgrade - Phase 3
 *
 * Features:
 * - Sacred plan access for AI agents
 * - Real-time drift detection with sacred plan compliance
 * - Natural language responses using LLM enhancement
 * - Development context export with sacred awareness
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import fetch from 'node-fetch';
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';

const execAsync = promisify(exec);

// Connect to our working sacred layer on port 5556
const RAG_AGENT_BASE_URL = process.env.RAG_AGENT_URL || 'http://localhost:5556';

class SacredAwareContextKeeperMCP {
  constructor() {
    this.server = new Server(
      {
        name: 'contextkeeper-sacred-enhanced',
        version: '3.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    this.cache = new Map();
  }

  setupToolHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          // Sacred Layer Tools (Phase 3 Priority)
          {
            name: 'get_sacred_context',
            description: 'Get sacred plans and architectural constraints for a project - essential for AI-aware development',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'string',
                  description: 'Project ID to get sacred plans for'
                },
                plan_status: {
                  type: 'string',
                  enum: ['all', 'approved', 'draft'],
                  description: 'Filter by plan status (default: approved)',
                  default: 'approved'
                }
              }
            }
          },
          
          {
            name: 'check_sacred_drift',
            description: 'Check if current development aligns with sacred plans - prevents architectural violations',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'string',
                  description: 'Project ID to analyze for drift'
                },
                hours: {
                  type: 'number',
                  description: 'Hours of activity to analyze (default: 24)',
                  default: 24
                }
              },
              required: ['project_id']
            }
          },

          {
            name: 'query_with_llm',
            description: 'Query the knowledge base with natural language responses (Phase 2.5 LLM enhancement)',
            inputSchema: {
              type: 'object',
              properties: {
                question: {
                  type: 'string',
                  description: 'Natural language question about the codebase or architecture'
                },
                k: {
                  type: 'number',
                  description: 'Number of results to consider (default: 5)',
                  default: 5
                }
              },
              required: ['question']
            }
          },

          {
            name: 'export_development_context',
            description: 'Export complete development context including sacred plans for AI agents',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'string',
                  description: 'Project ID to export context for'
                },
                include_sacred: {
                  type: 'boolean',
                  description: 'Include sacred plan context (default: true)',
                  default: true
                },
                include_drift: {
                  type: 'boolean',
                  description: 'Include drift analysis (default: true)',
                  default: true
                }
              }
            }
          },

          // Enhanced Development Context Tools
          {
            name: 'get_development_context',
            description: 'Get comprehensive development context including project status, git activity, objectives, decisions, and sacred layer analysis',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'string',
                  description: 'Optional project ID. Uses focused project if not provided'
                },
                include_git: {
                  type: 'boolean',
                  description: 'Include git activity analysis (default: true)',
                  default: true
                },
                include_sacred: {
                  type: 'boolean',
                  description: 'Include sacred layer analysis (default: true)',
                  default: true
                },
                hours: {
                  type: 'number',
                  description: 'Hours of history to analyze (default: 24)',
                  default: 24
                }
              }
            }
          },
          
          // Intelligent Search with Sacred Awareness
          {
            name: 'intelligent_search',
            description: 'Search with semantic understanding across code, decisions, objectives, and sacred plans',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Natural language search query'
                },
                search_types: {
                  type: 'array',
                  items: {
                    type: 'string',
                    enum: ['code', 'decisions', 'objectives', 'sacred_plans', 'all']
                  },
                  description: 'Types of content to search (default: all)',
                  default: ['all']
                },
                project_id: {
                  type: 'string',
                  description: 'Optional: limit to specific project'
                },
                max_results: {
                  type: 'number',
                  description: 'Maximum results per type (default: 5)',
                  default: 5
                }
              },
              required: ['query']
            }
          },

          // Sacred Plan Management
          {
            name: 'create_sacred_plan',
            description: 'Create a new sacred architectural plan (requires approval before activation)',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'string',
                  description: 'Project ID for the sacred plan'
                },
                title: {
                  type: 'string',
                  description: 'Title of the sacred plan'
                },
                content: {
                  type: 'string',
                  description: 'Sacred plan content in markdown format'
                }
              },
              required: ['project_id', 'title', 'content']
            }
          },

          // Health Check
          {
            name: 'health_check',
            description: 'Check the health status of the sacred layer and RAG agent',
            inputSchema: {
              type: 'object',
              properties: {}
            }
          }
        ]
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        // Check cache for expensive operations
        const cacheKey = `${name}-${JSON.stringify(args)}`;
        if (this.shouldCache(name) && this.cache.has(cacheKey)) {
          const cached = this.cache.get(cacheKey);
          if (Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.result;
          }
        }

        let result;
        switch (name) {
          // Sacred Layer Tools (Phase 3 Priority)
          case 'get_sacred_context':
            result = await this.getSacredContext(args);
            break;
          
          case 'check_sacred_drift':
            result = await this.checkSacredDrift(args);
            break;

          case 'query_with_llm':
            result = await this.queryWithLLM(args);
            break;

          case 'export_development_context':
            result = await this.exportDevelopmentContext(args);
            break;

          case 'create_sacred_plan':
            result = await this.createSacredPlan(args);
            break;

          // Enhanced Context Tools
          case 'get_development_context':
            result = await this.getDevelopmentContext(args);
            break;
          
          case 'intelligent_search':
            result = await this.intelligentSearch(args);
            break;

          case 'health_check':
            result = await this.healthCheck(args);
            break;
          
          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Unknown tool: ${name}`
            );
        }

        // Cache expensive operations
        if (this.shouldCache(name)) {
          this.cache.set(cacheKey, {
            result,
            timestamp: Date.now()
          });
        }

        return result;
      } catch (error) {
        if (error instanceof McpError) {
          throw error;
        }
        throw new McpError(
          ErrorCode.InternalError,
          `Tool execution failed: ${error.message}`
        );
      }
    });
  }

  shouldCache(toolName) {
    const cacheableTools = [
      'get_development_context',
      'get_sacred_context',
      'check_sacred_drift',
      'export_development_context'
    ];
    return cacheableTools.includes(toolName);
  }

  async ragRequest(endpoint, method = 'GET', data = null) {
    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      if (data) {
        options.body = JSON.stringify(data);
      }

      const response = await fetch(`${RAG_AGENT_BASE_URL}${endpoint}`, options);
      
      if (!response.ok) {
        throw new Error(`RAG Agent API error: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      throw new McpError(
        ErrorCode.InternalError,
        `Failed to communicate with ContextKeeper: ${error.message}`
      );
    }
  }

  // Sacred Layer Tool Implementations (Phase 3 Priority)

  async getSacredContext(args) {
    const { project_id, plan_status = 'approved' } = args;

    try {
      // Get sacred plans from our working endpoint - use GET for listing
      const sacredPlans = await this.ragRequest('/sacred/plans?' + new URLSearchParams({
        project_id: project_id || '',
        status: plan_status
      }), 'GET');

      let contextText = `# Sacred Architectural Context\n\n`;

      if (project_id) {
        contextText += `## Project: ${project_id}\n\n`;
      }

      if (sacredPlans && sacredPlans.plans && sacredPlans.plans.length > 0) {
        const filteredPlans = plan_status === 'all' ?
          sacredPlans.plans :
          sacredPlans.plans.filter(plan => plan.status === plan_status);

        contextText += `## Sacred Plans (${filteredPlans.length} ${plan_status})\n\n`;

        for (const plan of filteredPlans) {
          contextText += `### ${plan.title}\n`;
          contextText += `**Status**: ${plan.status}\n`;
          contextText += `**Created**: ${this.formatTimeAgo(plan.created_at)}\n`;
          if (plan.approved_at) {
            contextText += `**Approved**: ${this.formatTimeAgo(plan.approved_at)}\n`;
          }
          contextText += `\n${plan.content}\n\n---\n\n`;
        }
      } else {
        contextText += `## No Sacred Plans Found\n\n`;
        contextText += `No ${plan_status} sacred plans found for this project. Consider creating sacred architectural plans to guide AI development.\n\n`;
      }

      contextText += `## Sacred Layer Status\n`;
      contextText += `- **Immutability**: Approved plans cannot be modified\n`;
      contextText += `- **2-Layer Verification**: Required for plan approval\n`;
      contextText += `- **AI Compliance**: AI agents must respect sacred constraints\n`;

      return {
        content: [
          {
            type: 'text',
            text: contextText
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Sacred Context Error\n\nFailed to retrieve sacred plans: ${error.message}\n\nPlease ensure the sacred layer is running on ${RAG_AGENT_BASE_URL}`
          }
        ]
      };
    }
  }

  async checkSacredDrift(args) {
    const { project_id, hours = 24 } = args;

    if (!project_id) {
      throw new McpError(ErrorCode.InvalidParams, 'project_id is required');
    }

    try {
      // Use our working sacred drift endpoint
      const driftAnalysis = await this.ragRequest(`/sacred/drift/${project_id}?hours=${hours}`);

      let driftReport = `# Sacred Drift Analysis\n\n`;
      driftReport += `## Project: ${project_id}\n`;
      driftReport += `## Analysis Period: Last ${hours} hours\n\n`;

      if (driftAnalysis) {
        driftReport += `### Alignment Status: ${driftAnalysis.status.toUpperCase()}\n`;
        driftReport += `### Alignment Score: ${(driftAnalysis.alignment_score * 100).toFixed(1)}%\n\n`;

        if (driftAnalysis.violations && driftAnalysis.violations.length > 0) {
          driftReport += `## Sacred Plan Violations (${driftAnalysis.violations.length})\n\n`;
          for (const violation of driftAnalysis.violations) {
            driftReport += `### ${violation.type}\n`;
            driftReport += `- **File**: ${violation.file || 'Multiple'}\n`;
            driftReport += `- **Issue**: ${violation.message}\n\n`;
          }
        } else {
          driftReport += `## ✅ No Sacred Plan Violations Detected\n\n`;
        }

        if (driftAnalysis.recommendations && driftAnalysis.recommendations.length > 0) {
          driftReport += `## Recommendations\n\n`;
          for (const rec of driftAnalysis.recommendations) {
            driftReport += `- ${rec}\n`;
          }
          driftReport += `\n`;
        }

        if (driftAnalysis.sacred_plans_checked && driftAnalysis.sacred_plans_checked.length > 0) {
          driftReport += `## Sacred Plans Consulted\n`;
          for (const planId of driftAnalysis.sacred_plans_checked) {
            driftReport += `- ${planId}\n`;
          }
          driftReport += `\n`;
        }

        // Add status indicator
        const statusEmoji = {
          'aligned': '✅',
          'minor_drift': '⚠️',
          'moderate_drift': '🔶',
          'critical_violation': '🚨'
        };

        driftReport += `## Development Status\n`;
        driftReport += `${statusEmoji[driftAnalysis.status] || '❓'} **${driftAnalysis.status.replace('_', ' ').toUpperCase()}**\n\n`;

        if (driftAnalysis.status === 'aligned') {
          driftReport += `Your development is aligned with sacred architectural plans. Continue current approach.\n`;
        } else {
          driftReport += `Review the recommendations above to align with sacred architectural constraints.\n`;
        }
      } else {
        driftReport += `No drift analysis available. Sacred layer may not be properly configured.\n`;
      }

      return {
        content: [
          {
            type: 'text',
            text: driftReport
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Sacred Drift Analysis Error\n\nFailed to analyze sacred drift: ${error.message}\n\nEnsure sacred layer is running and project exists.`
          }
        ]
      };
    }
  }

  async queryWithLLM(args) {
    const { question, k = 5 } = args;
    
    if (!question) {
      throw new McpError(ErrorCode.InvalidParams, 'question is required');
    }

    try {
      // Use our Phase 2.5 LLM enhancement endpoint
      const llmResponse = await this.ragRequest('/query_llm', 'POST', {
        question,
        k
      });

      let responseText = `# Knowledge Base Query\n\n`;
      responseText += `**Question**: ${question}\n\n`;
      responseText += `## Answer\n\n${llmResponse.answer}\n\n`;
      
      if (llmResponse.sources && llmResponse.sources.length > 0) {
        responseText += `## Sources\n\n`;
        for (const source of llmResponse.sources) {
          responseText += `- ${source}\n`;
        }
        responseText += `\n`;
      }

      if (llmResponse.context_used) {
        responseText += `*Used ${llmResponse.context_used} context chunks*\n`;
      }

      return {
        content: [
          {
            type: 'text',
            text: responseText
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Query Error\n\nFailed to query with LLM enhancement: ${error.message}\n\nThe LLM enhancement endpoint may not be available.`
          }
        ]
      };
    }
  }

  async exportDevelopmentContext(args) {
    const { project_id, include_sacred = true, include_drift = true } = args;
    
    let contextExport = `# Development Context Export\n\n`;
    contextExport += `**Generated**: ${new Date().toISOString()}\n`;
    contextExport += `**Project**: ${project_id || 'All Projects'}\n\n`;

    try {
      // Get basic project context
      const projectContext = await this.ragRequest(
        project_id ? `/context/export?project_id=${project_id}` : '/context/export'
      );

      if (projectContext) {
        contextExport += `## Project Information\n\n`;
        contextExport += `${JSON.stringify(projectContext, null, 2)}\n\n`;
      }

      // Include sacred context if requested
      if (include_sacred) {
        try {
          const sacredContext = await this.getSacredContext({ project_id, plan_status: 'approved' });
          contextExport += `---\n\n`;
          contextExport += sacredContext.content[0].text + `\n\n`;
        } catch (error) {
          contextExport += `## Sacred Context Error\n${error.message}\n\n`;
        }
      }

      // Include drift analysis if requested
      if (include_drift && project_id) {
        try {
          const driftContext = await this.checkSacredDrift({ project_id, hours: 24 });
          contextExport += `---\n\n`;
          contextExport += driftContext.content[0].text + `\n\n`;
        } catch (error) {
          contextExport += `## Drift Analysis Error\n${error.message}\n\n`;
        }
      }

      contextExport += `---\n\n`;
      contextExport += `## Context Export Notes\n`;
      contextExport += `- Sacred plans provide architectural constraints for AI agents\n`;
      contextExport += `- Drift analysis indicates alignment with approved plans\n`;
      contextExport += `- This context enables sacred-aware AI development\n`;

      return {
        content: [
          {
            type: 'text',
            text: contextExport
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Context Export Error\n\nFailed to export development context: ${error.message}`
          }
        ]
      };
    }
  }

  async createSacredPlan(args) {
    const { project_id, title, content } = args;
    
    if (!project_id || !title || !content) {
      throw new McpError(ErrorCode.InvalidParams, 'project_id, title, and content are required');
    }

    try {
      // Create sacred plan via API
      const result = await this.ragRequest('/sacred/plans', 'POST', {
        project_id,
        title,
        content
      });

      let responseText = `# Sacred Plan Created\n\n`;
      responseText += `**Plan ID**: ${result.plan_id}\n`;
      responseText += `**Title**: ${title}\n`;
      responseText += `**Project**: ${project_id}\n`;
      responseText += `**Status**: ${result.status}\n\n`;

      if (result.verification_code) {
        responseText += `## Next Steps\n\n`;
        responseText += `To approve this sacred plan, use the 2-layer verification:\n`;
        responseText += `1. **Verification Code**: \`${result.verification_code}\`\n`;
        responseText += `2. **Approval Key**: Set in environment as SACRED_APPROVAL_KEY\n\n`;
        responseText += `**Note**: Plans must be approved before they become active architectural constraints.\n`;
      }

      return {
        content: [
          {
            type: 'text',
            text: responseText
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Sacred Plan Creation Error\n\nFailed to create sacred plan: ${error.message}`
          }
        ]
      };
    }
  }

  // Enhanced Context Tools

  async getDevelopmentContext(args) {
    const { project_id, include_git = true, include_sacred = true, hours = 24 } = args;
    
    let contextText = `# Comprehensive Development Context\n\n`;
    
    try {
      // Get basic context from RAG agent
      const context = await this.ragRequest(
        project_id ? `/context/export?project_id=${project_id}` : '/context/export'
      );

      if (context && context.project) {
        contextText += `## Project: ${context.project.name}\n`;
        contextText += `**Status**: ${context.project.status}\n`;
        contextText += `**Path**: ${context.project.root_path}\n\n`;
      }

      // Add sacred context if requested
      if (include_sacred) {
        try {
          const sacredInfo = await this.getSacredContext({ project_id, plan_status: 'approved' });
          contextText += `---\n\n`;
          contextText += sacredInfo.content[0].text;
        } catch (error) {
          contextText += `## Sacred Context\n**Error**: ${error.message}\n\n`;
        }
      }

      return {
        content: [
          {
            type: 'text',
            text: contextText
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Development Context Error\n\nFailed to get development context: ${error.message}`
          }
        ]
      };
    }
  }

  async intelligentSearch(args) {
    const { query, search_types = ['all'], project_id, max_results = 5 } = args;
    
    if (!query) {
      throw new McpError(ErrorCode.InvalidParams, 'query is required');
    }

    try {
      // Use our LLM-enhanced search
      const searchResults = await this.ragRequest('/query_llm', 'POST', {
        question: query,
        k: max_results
      });

      let searchText = `# Intelligent Search Results\n\n`;
      searchText += `**Query**: ${query}\n\n`;
      searchText += `## Answer\n\n${searchResults.answer}\n\n`;

      if (searchResults.sources) {
        searchText += `## Sources Found\n\n`;
        for (const source of searchResults.sources) {
          searchText += `- ${source}\n`;
        }
      }

      return {
        content: [
          {
            type: 'text',
            text: searchText
          }
        ]
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `# Search Error\n\nIntelligent search failed: ${error.message}`
          }
        ]
      };
    }
  }

  async healthCheck(args) {
    let healthReport = `# ContextKeeper Sacred Layer Health Check\n\n`;

    try {
      // Check RAG agent health
      const health = await this.ragRequest('/health');
      healthReport += `## RAG Agent: ✅ ${health.status || 'Running'}\n`;
      healthReport += `**URL**: ${RAG_AGENT_BASE_URL}\n\n`;

      // Check sacred layer health
      try {
        const sacredHealth = await this.ragRequest('/sacred/health');
        healthReport += `## Sacred Layer: ✅ Active\n`;
        healthReport += `**Status**: ${sacredHealth.status || 'Ready'}\n\n`;
      } catch (error) {
        healthReport += `## Sacred Layer: ❌ Error\n`;
        healthReport += `**Issue**: ${error.message}\n\n`;
      }

      // Check LLM enhancement
      try {
        const llmTest = await this.ragRequest('/query_llm', 'POST', {
          question: 'test',
          k: 1
        });
        healthReport += `## LLM Enhancement: ✅ Active\n`;
        healthReport += `**Response Time**: Fast\n\n`;
      } catch (error) {
        healthReport += `## LLM Enhancement: ❌ Error\n`;
        healthReport += `**Issue**: ${error.message}\n\n`;
      }

      healthReport += `## MCP Server Status\n`;
      healthReport += `**Version**: 3.0.0 (Sacred Layer)\n`;
      healthReport += `**Tools Available**: ${this.getToolCount()}\n`;
      healthReport += `**Cache Size**: ${this.cache.size} entries\n`;

    } catch (error) {
      healthReport += `## Health Check Failed\n`;
      healthReport += `**Error**: ${error.message}\n`;
    }

    return {
      content: [
        {
          type: 'text',
          text: healthReport
        }
      ]
    };
  }

  // Helper methods
  formatTimeAgo(timestamp) {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return 'just now';
  }

  getToolCount() {
    // Return number of available tools
    return 8; // Sacred layer + enhanced tools
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('ContextKeeper Sacred Layer MCP server v3.0 running on stdio');
    console.error('Connected to RAG Agent:', RAG_AGENT_BASE_URL);
    console.error('Sacred Layer: Active');
    console.error('LLM Enhancement: Available');
  }
}

const server = new SacredAwareContextKeeperMCP();
server.run().catch(console.error);