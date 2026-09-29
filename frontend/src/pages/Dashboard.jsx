import { useEffect, useState } from "react";
import {
  Users,
  Sparkles,
  TrendingUp,
  CircleDollarSign,
  Target,
  ArrowUpRight,
} from "lucide-react";

import KpiCard from "../components/dashboard/kpicard";
import PremiumCard from "../components/ui/PremiumCard";

import { getDashboardOverview } from "../services/dashboardService";

import AISection from "../components/ai/AISection";

export default function Dashboard() {

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true);
        setError("");

        const result = await getDashboardOverview();

        console.log("Dashboard API response:", result);

        setData(result);
      } catch (err) {
        console.error(err);
        setError(err.message || "Unable to load dashboard");
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner"></div>

        <p>
          Loading LeadForge intelligence...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-card">
        <h2>Unable to load dashboard</h2>

        <p>{error}</p>

        <button
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  }

  const totalLeads =
    data?.total_leads ??
    data?.total_analyses ??
    0;

  const hotLeads =
    data?.hot_leads ??
    data?.high_priority ??
    0;

  const qualifiedLeads =
    data?.qualified_leads ??
    0;

  const averageScore =
    data?.average_lead_score ??
    data?.average_score ??
    0;

  const recentLeads =
    data?.recent_analyses ??
    data?.recent_leads ??
    [];



    

  /*
   * Pipeline visualization.
   *
   * We only use metrics that are already
   * available in the dashboard response.
   */

  const pipelineItems = [
    {
      label: "Total Leads",
      value: totalLeads,
      percentage: 100,
      type: "total",
    },
    {
      label: "Hot Leads",
      value: hotLeads,
      percentage:
        totalLeads > 0
          ? Math.round((hotLeads / totalLeads) * 100)
          : 0,
      type: "hot",
    },
    {
      label: "Qualified",
      value: qualifiedLeads,
      percentage:
        totalLeads > 0
          ? Math.round(
              (qualifiedLeads / totalLeads) * 100
            )
          : 0,
      type: "qualified",
    },
  ];

  return (
  
      <div className="dashboard">

      {/* HEADER */}

      
      {/* KPI CARDS */}

 <div className="dashboard-header aurora-header">
  <div className="dashboard-title-section">
    

          

          <div className="welcome-banner">

           <div>

            <h2>Hi, Pranta! 👋</h2>

            <p>

            Your AI-powered command center is ready.

            </p>

            </div>

            <div className="welcome-pill">

            LIVE

           </div>

            </div>
        

    
       <div
     
       >
     <p>
      LeadForge v1.0.1
     </p>
   </div>

      </div>
     </div>


 <div className="kpi-grid">
  <KpiCard
    title="Total Leads"
    value={data?.total_leads ?? 0}
    icon={<Users />}
    color="#7C6CF8"
  />

  <KpiCard
    title="AI Qualified"
    value={data?.qualified ?? 0}
    icon={<Sparkles />}
    color="#A8C8A2"
  />

  <KpiCard
    title="Converted"
    value={data?.converted ?? 0}
    icon={<CircleDollarSign />}
    color="#F8E8A6"
  />

  <KpiCard
    title="Conversion Rate"
    value={`${data?.conversion_rate ?? 0}%`}
    icon={<TrendingUp />}
    color="#B7D8F8"
  />
 </div>

 <div className="ai-activity-wrapper">
  <PremiumCard>
    <div className="ai-activity">
      <div>
        <h3>AI Intelligence Center</h3>
        <p>
          Your AI Lead Brain has already identified{" "}
          <strong>{data?.qualified ?? 0}</strong> qualified opportunities ready for your Sales team.
        </p>
      </div>
      <AISection/>
      <div
        style={{
          width: 72,
          height: 72,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          borderRadius: "22px",
          background: "linear-gradient(135deg,#7C6CF8,#B7D8F8)",
          color: "#fff",
        }}
      >
        <Sparkles size={32} color="#5CA9FF" />
      </div>
    </div>
  </PremiumCard>
 </div>

 {/* DASHBOARD PANELS */}
 
      <div className="dashboard-grid">

        {/* PIPELINE */}

        <div className="dashboard-panel">

          <div className="panel-heading">

            <div>
              <div className="section-eyebrow">
                INTELLIGENCE
              </div>

              <h2>Pipeline Overview</h2>
            </div>

          </div>

          <div className="pipeline-list">

            {pipelineItems.map((item) => (

              <div
                className="pipeline-item"
                key={item.label}
              >

                <div className="pipeline-item-header">

                  <div className="pipeline-label">
                    <span
                      className={`pipeline-indicator ${item.type}`}
                    />

                    <span>
                      {item.label}
                    </span>
                  </div>

                  <strong>
                    {item.value}
                  </strong>

                </div>


                <div className="pipeline-track">

                  <div
                    className={`pipeline-fill ${item.type}`}
                    style={{
                      width: `${item.percentage}%`,
                    }}
                  />

                </div>


                <span className="pipeline-percentage">
                  {item.percentage}% of tracked leads
                </span>

              </div>

            ))}

          </div>

        </div>


        {/* LEAD QUALITY */}

        <div className="dashboard-panel">

          <div className="panel-heading">

            <div>
              <div className="section-eyebrow">
                PRIORITY
              </div>

              <h2>Lead Quality</h2>
            </div>

            <Target size={18} />

          </div>


          <div className="quality-summary">

            <div>
              <strong>{hotLeads}</strong>
              <span>Hot</span>
            </div>

            <div>
              <strong>{qualifiedLeads}</strong>
              <span>Qualified</span>
            </div>

            <div>
              <strong>
                {averageScore
                  ? Number(averageScore).toFixed(0)
                  : 0}
              </strong>

              <span>Avg Score</span>
            </div>

          </div>


          <div className="quality-insight">

            <div className="quality-insight-icon">
              <ArrowUpRight size={16} />
            </div>

            <div>
              <strong>
                Intelligence coverage
              </strong>

              <span>
                Lead scoring and AI analysis
                are available in the Intelligence
                workspace.
              </span>
            </div>

          </div>

        </div>

      </div>


      {/* RECENT LEADS */}

      

    </div>
  
  );
}

