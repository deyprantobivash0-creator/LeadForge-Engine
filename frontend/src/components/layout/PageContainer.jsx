function PageContainer({ children }) {
  return (
    <main className="page-container" id="main-content" tabIndex={-1}>
      {children}
    </main>
  );
}

export default PageContainer;