import { useState } from "react";

const PROVIDERS = [
  { key: "openai", label: "OpenAI 兼容" },
  { key: "anthropic", label: "Anthropic 兼容" },
];

export default function SettingsModal({ settings, onSave, onClose }) {
  const [provider, setProvider] = useState(settings.provider);
  const [apiKey, setApiKey] = useState(settings.apiKey);
  const [baseUrl, setBaseUrl] = useState(settings.baseUrl);
  const [model, setModel] = useState(settings.model);

  const handleSave = () => {
    onSave({ provider, apiKey, baseUrl, model });
    onClose();
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="settings-overlay" onClick={handleOverlayClick}>
      <div className="settings-panel">
        <div className="settings-header">
          <h3>设置</h3>
          <button className="btn-close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>

        <div className="provider-tabs">
          {PROVIDERS.map((p) => (
            <button
              key={p.key}
              className={`provider-tab${provider === p.key ? " active" : ""}`}
              onClick={() => setProvider(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="form-group">
          <label htmlFor="settings-apikey">API Key</label>
          <input
            id="settings-apikey"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="settings-baseurl">Base URL（可选）</label>
          <input
            id="settings-baseurl"
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={provider === "openai" ? "https://api.openai.com/v1" : "https://api.anthropic.com"}
          />
        </div>

        <div className="form-group">
          <label htmlFor="settings-model">Model</label>
          <input
            id="settings-model"
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={provider === "openai" ? "gpt-4o" : "claude-sonnet-4-20250514"}
          />
        </div>

        <button className="btn-save" onClick={handleSave}>
          保存
        </button>
      </div>
    </div>
  );
}
