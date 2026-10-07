export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const quizId = url.searchParams.get('id') || url.searchParams.get('quiz_id');
    
    let targetQuizId = quizId;
    if (!targetQuizId) {
      const match = url.pathname.match(/^\/quiz\/([^\/]+)/);
      if (match) targetQuizId = match[1];
    }

    // Bỏ qua các tệp tĩnh (CSS, JS, hình ảnh, font chữ)
    if (url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map)$/i)) {
      return env.ASSETS.fetch(request);
    }

    // Tải tệp HTML gốc từ bộ nhớ đệm Cloudflare Pages
    let response = await env.ASSETS.fetch(request);
    const contentType = response.headers.get('content-type') || '';
    if (!response.ok || !contentType.includes('text/html')) {
      return response;
    }

    const origin = url.origin;
    const absoluteOgImage = `${origin}/unnamed.jpg`;

    // Nếu không có mã đề thi, đảm bảo các thẻ ảnh và link là URL tuyệt đối
    if (!targetQuizId) {
      return new HTMLRewriter()
        .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
        .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
        .transform(response);
    }

    // Khi có mã đề thi: Edge Worker truy vấn máy chủ Koyeb để lấy tên đề thi thực tế
    try {
      const backendUrl = `https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app/api/get_quiz/${targetQuizId}`;
      const backendRes = await fetch(backendUrl, {
        headers: { 'User-Agent': 'Cloudflare-Pages-Edge/1.0' }
      });
      if (backendRes.ok) {
        const quizData = await backendRes.json();
        if (quizData.status === 'success' && quizData.title) {
          const rawTitle = quizData.title.trim();
          const pageTitle = `${rawTitle} - HocNhanhTN`;
          const qCount = Array.isArray(quizData.data) ? quizData.data.length : 0;
          const timeLimit = quizData.time_limit || 0;
          
          let desc = `Đề thi: ${rawTitle}`;
          if (qCount > 0) desc += ` • ${qCount} câu hỏi`;
          if (timeLimit > 0) desc += ` • ${timeLimit} phút làm bài`;
          desc += `. Hệ thống học nhanh trắc nghiệm chuẩn GDPT 2018 trên HocNhanhTN.`;

          return new HTMLRewriter()
            .on('title', { element(el) { el.setInnerContent(pageTitle); } })
            .on('meta[property="og:title"]', { element(el) { el.setAttribute('content', rawTitle); } })
            .on('meta[name="twitter:title"]', { element(el) { el.setAttribute('content', rawTitle); } })
            .on('meta[name="description"]', { element(el) { el.setAttribute('content', desc); } })
            .on('meta[property="og:description"]', { element(el) { el.setAttribute('content', desc); } })
            .on('meta[name="twitter:description"]', { element(el) { el.setAttribute('content', desc); } })
            .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
            .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
            .transform(response);
        }
      }
    } catch (err) {
      // Nếu có lỗi kết nối backend, trả về HTML mặc định với ảnh tuyệt đối
    }

    return new HTMLRewriter()
      .on('meta[property="og:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[property="og:image:secure_url"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[name="twitter:image"]', { element(el) { el.setAttribute('content', absoluteOgImage); } })
      .on('meta[property="og:url"]', { element(el) { el.setAttribute('content', url.href); } })
      .transform(response);
  }
};
