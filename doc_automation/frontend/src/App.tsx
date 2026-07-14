import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  Trash2, 
  Loader, 
  Download, 
  RefreshCw, 
  FileUp, 
  File, 
  Folder, 
  ArrowRight,
  Database
} from 'lucide-react';


export default function App() {
  // App step: 'upload' | 'processing' | 'results'
  const [step, setStep] = useState<'upload' | 'processing' | 'results'>('upload');
  
  // Files State
  const [sources, setSources] = useState<File[]>([]);
  const [planTemplate, setPlanTemplate] = useState<File | null>(null);
  const [incubationTemplate, setIncubationTemplate] = useState<File | null>(null);
  
  // Processing & Polling State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>('Initializing...');
  const [backendStatus, setBackendStatus] = useState<'PENDING' | 'EXTRACTING' | 'AI_PROCESSING' | 'EDITING' | 'DONE' | 'FAILED'>('PENDING');
  
  // Final Results State
  const [projects, setProjects] = useState<string[]>([]);
  const [outputFiles, setOutputFiles] = useState<string[]>([]);
  const [zipReady, setZipReady] = useState<boolean>(false);
  
  // Server Health Status
  const [serverHealth, setServerHealth] = useState<{ connected: boolean; ai: string } | null>(null);

  // Check Backend Connection on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await axios.get('/health');
        if (res.data && res.data.status === 'ok') {
          setServerHealth({ connected: true, ai: res.data.ai });
        }
      } catch (err) {
        setServerHealth({ connected: false, ai: '' });
      }
    };
    checkHealth();
  }, []);

  // Format Bytes to human readable
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Drag and Drop State for Sources
  const [dragOverSources, setDragOverSources] = useState<boolean>(false);

  // File Handlers
  const handleSourceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setSources(prev => [...prev, ...newFiles]);
      toast.success(`Added ${newFiles.length} source file(s)`);
    }
  };

  const removeSource = (index: number) => {
    setSources(prev => prev.filter((_, i) => i !== index));
  };

  const handleTemplateChange = (role: 'plan' | 'incubation', file: File | null) => {
    if (!file) return;
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Template must be a PDF file.');
      return;
    }
    if (role === 'plan') {
      setPlanTemplate(file);
      toast.success('Plan Template selected');
    } else {
      setIncubationTemplate(file);
      toast.success('Incubation Template selected');
    }
  };

  // Drag and drop for sources
  const handleSourceDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOverSources(false);
    if (e.dataTransfer.files) {
      const newFiles = Array.from(e.dataTransfer.files);
      setSources(prev => [...prev, ...newFiles]);
      toast.success(`Dropped ${newFiles.length} source file(s)`);
    }
  };

  // Main Submit Pipeline
  const startPipeline = async () => {
    if (sources.length === 0) {
      toast.error('Please upload at least one source document.');
      return;
    }
    if (!planTemplate || !incubationTemplate) {
      toast.error('Please upload both the Plan and Incubation PDF templates.');
      return;
    }

    try {
      setStep('processing');
      setProgress(5);
      setStatusMessage('Uploading files to the server...');
      
      const formData = new FormData();
      sources.forEach(file => {
        formData.append('source_files', file);
      });
      formData.append('plan_template', planTemplate);
      formData.append('incubation_template', incubationTemplate);

      // 1. Upload files
      const uploadRes = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      const sid = uploadRes.data.session_id;
      setSessionId(sid);
      setProgress(15);
      setStatusMessage('Files uploaded. Triggering AI analysis...');

      await axios.post('/api/process', { session_id: sid });
      
      // 3. Poll Status
      pollStatus(sid);

    } catch (err: any) {
      console.error(err);
      const errMsg = err.response?.data?.detail || 'Failed to upload files. Please try again.';
      toast.error(errMsg);
      setStep('upload');
    }
  };

  // Poll status endpoint
  const pollStatus = (sid: string) => {
    const interval = setInterval(async () => {
      try {
        const statusRes = await axios.get(`/api/process/${sid}/status`);
        const { status, progress, message, error } = statusRes.data;
        
        setProgress(progress);
        setStatusMessage(message);
        setBackendStatus(status);

        if (status === 'done') {
          clearInterval(interval);
          toast.success('Processing complete!');
          fetchFinalResults(sid);
        } else if (status === 'failed') {
          clearInterval(interval);
          toast.error(error || 'Processing failed.');
          // stay in processing state but show error details
        }
      } catch (err) {
        console.error('Error polling status', err);
      }
    }, 1500);
  };

  // Fetch final results
  const fetchFinalResults = async (sid: string) => {
    try {
      const res = await axios.get(`/api/process/${sid}/result`);
      setProjects(res.data.projects);
      setOutputFiles(res.data.output_files);
      setZipReady(!!res.data.zip_path);
      setStep('results');
    } catch (err) {
      toast.error('Failed to load processing results.');
    }
  };

  // Helper to extract file name from path
  const getFilenameFromPath = (path: string): string => {
    return path.replace(/\\/g, '/').split('/').pop() || '';
  };

  // Reset State to Start Over
  const resetSession = () => {
    setStep('upload');
    setSources([]);
    setPlanTemplate(null);
    setIncubationTemplate(null);
    setSessionId(null);
    setProgress(0);
    setStatusMessage('Initializing...');
    setBackendStatus('PENDING');
    setProjects([]);
    setOutputFiles([]);
    setZipReady(false);
  };

  return (
    <div className="app-container">
      <Toaster position="top-right" />
      
      {/* Header */}
      <header className="app-header">
        <div className="app-logo">AI Document Automation</div>
        <p className="app-subtitle">
          Upload project documents and PDF templates. Our AI extracts core data and dynamically populates templates in-place.
        </p>

        {/* Server Connection Status badge */}
        <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'center', gap: '10px' }}>
          {serverHealth ? (
            serverHealth.connected ? (
              <span className="project-tag" style={{ border: '1px solid rgba(16, 185, 129, 0.4)', background: 'rgba(16, 185, 129, 0.05)', color: '#10B981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="step-indicator" style={{ width: '8px', height: '8px', border: 'none', background: '#10B981' }}></span>
                Backend Connected (AI: {serverHealth.ai.toUpperCase()})
              </span>
            ) : (
              <span className="project-tag" style={{ border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.05)', color: '#EF4444', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="step-indicator" style={{ width: '8px', height: '8px', border: 'none', background: '#EF4444' }}></span>
                Backend Disconnected
              </span>
            )
          ) : (
            <span className="project-tag" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Loader className="step-indicator" style={{ width: '8px', height: '8px', border: 'none', animation: 'spin 1s linear infinite' }} />
              Checking Connection...
            </span>
          )}
        </div>
      </header>

      {/* Main Panel */}
      <main className="glass-panel" style={{ flexGrow: 1, overflow: 'hidden' }}>
        
        {/* Upload Step */}
        {step === 'upload' && (
          <div style={{ padding: '32px' }}>
            <div className="dashboard-grid">
              
              {/* Left Column: Source Documents */}
              <div>
                <h3 className="section-title">
                  <FileUp size={20} />
                  1. Source Project Documents
                </h3>
                <div className="upload-card" style={{ background: 'rgba(0, 0, 0, 0.15)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(255, 255, 255, 0.03)' }}>
                  <div 
                    className={`dropzone ${dragOverSources ? 'active' : ''}`}
                    onDragOver={(e) => { e.preventDefault(); setDragOverSources(true); }}
                    onDragLeave={() => setDragOverSources(false)}
                    onDrop={handleSourceDrop}
                    onClick={() => document.getElementById('sources-input')?.click()}
                  >
                    <input 
                      type="file" 
                      id="sources-input" 
                      multiple 
                      style={{ display: 'none' }} 
                      onChange={handleSourceChange}
                      accept=".pdf,.docx,.pptx,.doc,.ppt"
                    />
                    <div className="dropzone-icon">
                      <Upload size={24} />
                    </div>
                    <p className="dropzone-title">Drag & Drop project files here</p>
                    <p className="dropzone-desc">or click to browse from folder</p>
                    <p className="dropzone-desc" style={{ marginTop: '10px', fontSize: '0.75rem', opacity: 0.7 }}>
                      Supports PDF, DOCX, PPTX (Max 50MB per file)
                    </p>
                  </div>

                  {/* Sources List */}
                  {sources.length > 0 && (
                    <div className="file-list">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', padding: '0 4px' }}>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Selected ({sources.length})</span>
                        <button 
                          onClick={() => setSources([])} 
                          style={{ background: 'none', border: 'none', color: 'var(--error)', fontSize: '0.8rem', cursor: 'pointer' }}
                        >
                          Clear All
                        </button>
                      </div>
                      {sources.map((file, idx) => (
                        <div key={idx} className="file-item">
                          <div className="file-info">
                            <FileText size={18} className="file-icon" />
                            <div className="file-details">
                              <div className="file-name" title={file.name}>{file.name}</div>
                              <div className="file-size">{formatBytes(file.size)}</div>
                            </div>
                          </div>
                          <button className="btn-remove" onClick={() => removeSource(idx)}>
                            <Trash2 size={16} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Templates */}
              <div>
                <h3 className="section-title">
                  <Database size={20} />
                  2. Target PDF Templates
                </h3>
                <div className="template-grid">
                  
                  {/* Plan Template */}
                  <div className="template-box">
                    <div className="template-label">
                      <span>Plan</span>
                      Plan PDF Template
                    </div>
                    <div 
                      className={`template-slot ${planTemplate ? 'filled' : ''}`}
                      onClick={() => document.getElementById('plan-input')?.click()}
                    >
                      <input 
                        type="file" 
                        id="plan-input" 
                        style={{ display: 'none' }} 
                        accept=".pdf"
                        onChange={(e) => handleTemplateChange('plan', e.target.files?.[0] || null)}
                      />
                      {planTemplate ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                          <CheckCircle size={28} style={{ color: 'var(--success)' }} />
                          <div className="file-name" style={{ maxWidth: '100%' }} title={planTemplate.name}>
                            {planTemplate.name}
                          </div>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Click to replace</span>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', opacity: 0.8 }}>
                          <File size={28} style={{ color: 'var(--text-dim)' }} />
                          <span style={{ fontSize: '0.85rem' }}>Upload Plan Template</span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>PDF formats only</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Incubation Template */}
                  <div className="template-box">
                    <div className="template-label">
                      <span>Incubation</span>
                      Incubation PDF Template
                    </div>
                    <div 
                      className={`template-slot ${incubationTemplate ? 'filled' : ''}`}
                      onClick={() => document.getElementById('incubation-input')?.click()}
                    >
                      <input 
                        type="file" 
                        id="incubation-input" 
                        style={{ display: 'none' }} 
                        accept=".pdf"
                        onChange={(e) => handleTemplateChange('incubation', e.target.files?.[0] || null)}
                      />
                      {incubationTemplate ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                          <CheckCircle size={28} style={{ color: 'var(--success)' }} />
                          <div className="file-name" style={{ maxWidth: '100%' }} title={incubationTemplate.name}>
                            {incubationTemplate.name}
                          </div>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Click to replace</span>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', opacity: 0.8 }}>
                          <File size={28} style={{ color: 'var(--text-dim)' }} />
                          <span style={{ fontSize: '0.85rem' }}>Upload Incubation Template</span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>PDF formats only</span>
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              </div>

            </div>

            {/* Submit Section */}
            <div className="action-panel" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '32px' }}>
              <button 
                className="btn-primary" 
                onClick={startPipeline}
                disabled={sources.length === 0 || !planTemplate || !incubationTemplate}
              >
                <span>Automate Document Mapping</span>
                <ArrowRight size={20} />
              </button>
            </div>
          </div>
        )}

        {/* Processing Step */}
        {step === 'processing' && (
          <div className="processing-container">
            
            {/* Animated SVG circular progress */}
            <div className="loader-container">
              <svg width="140" height="140" viewBox="0 0 100 100">
                <defs>
                  <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="var(--color-primary)" />
                    <stop offset="100%" stopColor="var(--color-accent)" />
                  </linearGradient>
                </defs>
                <circle cx="50" cy="50" r="42" className="progress-circle-bg" />
                <circle 
                  cx="50" 
                  cy="50" 
                  r="42" 
                  className="progress-circle-val" 
                  strokeDasharray="263.89" 
                  strokeDashoffset={263.89 - (263.89 * progress) / 100}
                />
              </svg>
              <div className="loader-percentage">{progress}%</div>
            </div>

            <h3 className="status-headline">
              {backendStatus === 'FAILED' ? 'Processing Failed' : 'Document Processing in Progress'}
            </h3>
            <p className="status-subtext">{statusMessage}</p>

            {/* Timeline Steps */}
            <div className="steps-timeline">
              <div className={`step-row ${progress >= 15 ? 'completed' : 'active'}`}>
                <div className="step-indicator">{progress >= 15 ? '✓' : '1'}</div>
                <div className="step-text">Upload project files & templates</div>
              </div>
              <div className={`step-row ${backendStatus === 'FAILED' ? '' : progress >= 30 ? 'completed' : progress >= 15 ? 'active' : ''}`}>
                <div className="step-indicator">{progress >= 30 ? '✓' : '2'}</div>
                <div className="step-text">Extract document raw texts</div>
              </div>
              <div className={`step-row ${backendStatus === 'FAILED' ? '' : progress >= 55 ? 'completed' : progress >= 30 ? 'active' : ''}`}>
                <div className="step-indicator">{progress >= 55 ? '✓' : '3'}</div>
                <div className="step-text">AI structured data extraction</div>
              </div>
              <div className={`step-row ${backendStatus === 'FAILED' ? '' : progress >= 92 ? 'completed' : progress >= 55 ? 'active' : ''}`}>
                <div className="step-indicator">{progress >= 92 ? '✓' : '4'}</div>
                <div className="step-text">Populate PDF templates (fitz)</div>
              </div>
              <div className={`step-row ${backendStatus === 'FAILED' ? '' : progress >= 100 ? 'completed' : progress >= 92 ? 'active' : ''}`}>
                <div className="step-indicator">{progress >= 100 ? '✓' : '5'}</div>
                <div className="step-text">Create ZIP archive package</div>
              </div>
            </div>

            {backendStatus === 'FAILED' && (
              <button 
                className="btn-secondary" 
                style={{ marginTop: '40px', maxWidth: '200px' }} 
                onClick={resetSession}
              >
                <RefreshCw size={16} />
                Try Again
              </button>
            )}
          </div>
        )}

        {/* Results Step */}
        {step === 'results' && (
          <div className="results-container">
            <div className="results-header">
              <div className="success-icon-badge">
                <CheckCircle size={40} />
              </div>
              <h3 className="status-headline">Automation Successful!</h3>
              <p className="app-subtitle" style={{ fontSize: '1rem' }}>
                AI has successfully extracted project details and generated the customized templates.
              </p>
            </div>

            {/* List of Detected Projects */}
            <div style={{ marginBottom: '24px' }}>
              <h4 className="section-title">
                <Folder size={18} />
                Generated Documents ({projects.length} Project{projects.length !== 1 ? 's' : ''} Found)
              </h4>
              
              <div className="project-cards-container">
                {projects.map((projName, idx) => {
                  // Find output files for this project
                  const safeName = projName.replace(/[^a-zA-Z0-9-_]/g, '_');
                  const planFile = outputFiles.find(f => f.includes(`${safeName}_Plan.pdf`));
                  const incubationFile = outputFiles.find(f => f.includes(`${safeName}_Incubation.pdf`));

                  return (
                    <div key={idx} className="project-card">
                      <div className="project-meta">
                        <div className="project-folder-icon">
                          <Folder size={22} />
                        </div>
                        <div className="project-details">
                          <div className="project-title-name" title={projName}>{projName}</div>
                          <span className="project-tag">AI Extracted</span>
                        </div>
                      </div>
                      
                      <div className="project-actions">
                        {planFile && (
                          <button 
                            className="btn-secondary"
                            onClick={() => window.open(`/api/download/${sessionId}/pdf/${getFilenameFromPath(planFile)}`, '_blank')}
                          >
                            <Download size={15} />
                            Download Plan PDF
                          </button>
                        )}
                        {incubationFile && (
                          <button 
                            className="btn-accent"
                            onClick={() => window.open(`/api/download/${sessionId}/pdf/${getFilenameFromPath(incubationFile)}`, '_blank')}
                          >
                            <Download size={15} />
                            Download Incubation PDF
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Footer Buttons */}
            <div className="results-footer">
              {zipReady && (
                <button 
                  className="btn-primary" 
                  onClick={() => window.open(`/api/download/${sessionId}/zip`, '_blank')}
                  style={{ flexGrow: 2 }}
                >
                  <Download size={20} />
                  Download All PDFs (.ZIP)
                </button>
              )}
              <button 
                className="btn-secondary" 
                onClick={resetSession}
                style={{ flexGrow: 1 }}
              >
                <RefreshCw size={18} />
                New Session
              </button>
            </div>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="app-footer">
        Powered by Google Gemini AI &bull; Built with React &amp; FastAPI &bull; 2026
      </footer>
    </div>
  );
}
